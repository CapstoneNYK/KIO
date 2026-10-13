import os
import re
import tempfile

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ai.recommend import qa_chain, recommend_chain
from ai.intent import classify_intent
from ai.fast_intent import fast_classify
from ai.entity import (
    extract_multi_order,
    extract_ordinal,
    extract_quantity,
    extract_attributes,
    extract_options_from_text,
    extract_option_details,
    extract_packaging,
)
from ai.payment import get_payment_response
from ai.discount import get_discount_tip
from ai.stt import transcribe as transcribe_audio
from ai.logging_utils import log_intent_query
from ai.order import (
    _is_noise_menu,
    apply_discount_menu_fallback,
    cart_answer,
    entities_to_orders,
    split_sold_out,
    validate_options,
)
from ai.cart_command import detect_cart_command
from ai.preference import find_alternatives, recommend_by_conditions
from app.coupon.router import router as coupon_router
from app.admin import db as admin_db
from app.admin.db import UPLOAD_DIR
from app.admin.router import (
    router as admin_router,
    auth_router as admin_auth_router,
    discounts_public_router,
    menus_public_router,
    orders_router,
)

load_dotenv()

app = FastAPI()

# FRONTEND_URL에 콤마로 여러 주소를 넣을 수 있게 하고(.env: FRONTEND_URL=http://localhost:5173,http://192.168.0.17:5173),
# 추가로 같은 와이파이(192.168.x.x)나 Tailscale(100.x.x.x)로 접속하는 흔한 케이스는
# 정규식으로 한 번에 허용한다. PC를 서버로 쓰면서 다른 기기(노트북 등)로 접속할 때마다
# IP가 바뀌어서 매번 .env를 고쳐야 하는 번거로움을 줄이기 위함.
_frontend_urls = [u.strip() for u in os.getenv("FRONTEND_URL", "http://localhost:5173").split(",") if u.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_frontend_urls, os.getenv("ADMIN_URL", "http://localhost:5174")],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|100\.\d{1,3}\.\d{1,3}\.\d{1,3}):517[3-6]",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(coupon_router)
app.include_router(admin_auth_router)
app.include_router(admin_router)
app.include_router(orders_router)
app.include_router(menus_public_router)
app.include_router(discounts_public_router)

app.mount("/uploads/menu-images", StaticFiles(directory=UPLOAD_DIR), name="menu-images")

# 직전에 추천했던 메뉴 목록(순서 그대로). 카페 키오스크는 보통 한 번에 한 사람만
# 이용하므로 세션 관리 없이 전역 변수로 "방금 추천받은 목록"만 기억해두고,
# "그 중 1번으로 담아줘" 같은 후속 주문 발화를 해석하는 데 사용한다.
_last_recommended_menus: list[str] = []

# "T멤버십 할인되나요?"처럼 할인 관련 "질문"이 order로 잘못 분류됐을 때,
# 무작정 메뉴를 장바구니에 담아버리지 않고 안내 답변으로 처리하기 위한 패턴.
_DISCOUNT_QUESTION_PATTERN = re.compile(
    r"(\?|되나요|되나|돼요|되나여|가능해|가능한가|뭐야|뭐예요|뭔가요|얼마|무엇|알려줘)"
)


def _resolve_ordinal_order(query: str) -> dict | None:
    """"1번으로 담아줘"처럼 직전 추천 목록을 순서로 가리키는 발화를 주문 엔티티로 변환한다.
    해당 안 되면 None."""
    ordinal = extract_ordinal(query)
    if ordinal and 1 <= ordinal <= len(_last_recommended_menus):
        chosen_menu = _last_recommended_menus[ordinal - 1]
        return {
            "menu": chosen_menu,
            "quantity": extract_quantity(query),
            "attributes": extract_attributes(query),
            "options": extract_options_from_text(query),
            "option_details": extract_option_details(query),
            "packaging": extract_packaging(query),
            "needs_recommendation": False,
        }
    return None


def _alternatives_map(sold_out: list[str], menus: list[dict]) -> dict[str, list[str]]:
    """품절 메뉴별 대체 메뉴(같은 카테고리의 주문 가능한 메뉴)를 찾고, 첫 번째 목록을 '직전 추천'으로 기억한다."""
    alternatives = {}
    for name in sold_out:
        alts = find_alternatives(name, menus)
        if alts:
            alternatives[name] = alts
    if alternatives:
        _last_recommended_menus[:] = next(iter(alternatives.values()))
    return alternatives


def _recommend(query: str):
    """맞춤형 추천. 조건(맛/온도/카페인/가격/종류)이 잡히면 실제 메뉴 DB를 규칙으로 필터링하고,
    조건이 없는 막연한 요청만 LLM 추천으로 넘긴다."""
    by_rule = recommend_by_conditions(query, admin_db.get_menus())
    if by_rule is not None:
        return by_rule
    return recommend_chain.invoke(query)


def _order_response(
    question: str,
    orders: list[dict],
    named: list[dict],
    sold_out: list[str],
    menus: list[dict] | None = None,
    notices: list[str] | None = None,
) -> dict:
    """"장바구니에 담았습니다" 형태의 일반 주문 응답을 만든다.
    order 분기와, order_and_pay인데 실제로는 결제수단이 없거나 담을 메뉴가 없어서
    order로 강등되는 경우에서 공용으로 쓴다.
    품절 메뉴가 있으면 같은 카테고리의 대체 메뉴를 함께 안내하고, 그 목록을
    '직전 추천'으로 기억해 "1번으로 담아줘" 같은 후속 발화를 받을 수 있게 한다."""
    alternatives = _alternatives_map(sold_out, menus or [])
    return {
        "question": question,
        "intent": "order",
        "answer": cart_answer(named, sold_out, alternatives=alternatives, notices=notices),
        "orders": orders,
        "discount_tip": get_discount_tip() if named else None,
        "sold_out": sold_out,
        "alternatives": alternatives,
    }


class QueryRequest(BaseModel):
    query: str
    cart_items: list[str] = []


@app.get("/")
def root():
    return {"msg": "hello"}


@app.post("/api/stt")
async def speech_to_text(file: UploadFile = File(...)):
    """녹음된 오디오를 받아 자체 호스팅 Whisper 모델로 텍스트를 반환한다.

    기존 브라우저 Web Speech API를 대체하는 엔드포인트로, 노이즈에 더 강인한
    인식을 위해 서버에서 VAD 필터가 적용된 faster-whisper로 인식한다.
    """
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="오디오 데이터가 비어있습니다.")

    suffix = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        text = transcribe_audio(tmp_path, language="ko")
    finally:
        os.unlink(tmp_path)

    if not text:
        raise HTTPException(status_code=422, detail="음성을 인식하지 못했습니다. 다시 말씀해 주세요.")

    return {"text": text}


@app.post("/api/recommend")
async def ask_menu(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문이 비어있습니다.")

    result = _recommend(request.query)
    _last_recommended_menus[:] = result.menus
    return {"question": request.query, "answer": result.answer, "recommended_menus": result.menus}


@app.post("/api/ask")
async def ask_intent(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문이 비어있습니다.")

    # 장바구니 취소·변경은 장바구니를 직접 바꾸는 동작이라 LLM 분류 전에 규칙으로 먼저 처리한다
    # (오분류 비용이 크고, 모호하면 실행하지 않고 되묻는다).
    all_menus = admin_db.get_menus()
    command = detect_cart_command(request.query, request.cart_items, all_menus)
    if command:
        return {"question": request.query, **command}

    # 확실한 발화는 규칙으로 즉시 분류하고(LLM 호출 생략), 애매할 때만 LLM에 맡긴다.
    intent = fast_classify(request.query, [m["name"] for m in all_menus]) or classify_intent(request.query)
    # 실사용 발화+예측 의도를 누적 기록 -> 나중에 검토 후 파인튜닝 데이터로 활용
    log_intent_query(request.query, intent)

    if intent == "order":
        menus = all_menus
        menu_names = [m["name"] for m in menus]
        sold_out_names = {m["name"] for m in menus if m["sold_out"]}

        entities = extract_multi_order(request.query, menu_names)

        if all(_is_noise_menu(e.get("menu")) for e in entities):
            ordinal_entity = _resolve_ordinal_order(request.query)
            if ordinal_entity:
                entities = [ordinal_entity]
            elif _DISCOUNT_QUESTION_PATTERN.search(request.query):
                # 의도 분류가 "order"로 잘못 나왔더라도, 문장이 질문형이면
                # (예: "T멤버십 할인되나요?") 장바구니에 담지 말고 정보로 답변한다.
                answer = qa_chain.invoke({"question": request.query, "cart_items": request.cart_items})
                return {"question": request.query, "intent": "qa", "answer": answer}
            else:
                entities = apply_discount_menu_fallback(entities, request.query, menu_names)

        orders_all = entities_to_orders(entities)
        orders, sold_out = split_sold_out(orders_all, sold_out_names)
        orders, notices = validate_options(orders, menus)
        named = [o for o in orders if o["menu"]]
        return _order_response(request.query, orders, named, sold_out, menus, notices)
    elif intent == "coupon":
        return {
            "question": request.query,
            "intent": "coupon",
            "answer": "쿠폰 바코드를 카메라로 스캔해볼게요!",
        }
    elif intent == "recommend":
        result = _recommend(request.query)
        _last_recommended_menus[:] = result.menus
        return {
            "question": request.query,
            "intent": intent,
            "answer": result.answer,
            "recommended_menus": result.menus,
        }
    elif intent == "order_and_pay":
        menus = all_menus
        menu_names = [m["name"] for m in menus]
        sold_out_names = {m["name"] for m in menus if m["sold_out"]}

        entities = extract_multi_order(request.query, menu_names)

        if all(not e.get("menu") for e in entities):
            ordinal_entity = _resolve_ordinal_order(request.query)
            if ordinal_entity:
                entities = [ordinal_entity]
            else:
                entities = apply_discount_menu_fallback(entities, request.query, menu_names)

        orders_all = entities_to_orders(entities)
        orders, sold_out = split_sold_out(orders_all, sold_out_names)
        orders, notices = validate_options(orders, menus)
        named = [o for o in orders if o["menu"]]
        _, payment_method = get_payment_response(request.query)

        if not payment_method:
            # 결제수단이 실제로 언급되지 않았는데도 로컬 LLM이 order_and_pay로
            # 잘못 분류하는 경우가 있다. 결제 화면으로 강제 이동시키지 않고
            # 그냥 주문(order)처럼 장바구니에만 담는다.
            return _order_response(request.query, orders, named, sold_out, menus, notices)

        if sold_out and not named:
            # 담을 수 있는 메뉴가 없으면 결제 화면으로 넘어가지 않도록 일반 주문 응답으로 돌려준다
            return _order_response(request.query, orders, named, sold_out, menus, notices)

        method_label = {
            "card": "카드", "kakao": "카카오페이", "naver": "네이버페이",
            "appcard": "앱카드", "voucher": "모바일상품권", "giftcard": "기프트카드",
            "kt": "KT VIP", "tmembership": "T멤버십", "cjone": "CJ ONE", "uzu": "T우주",
        }.get(payment_method or "", "")
        suffix = f" {method_label}로 결제 화면으로 이동합니다." if method_label else " 결제 화면으로 이동합니다."

        return {
            "question": request.query,
            "intent": "order_and_pay",
            "answer": cart_answer(
                named, sold_out, pay_suffix=suffix,
                alternatives=_alternatives_map(sold_out, menus), notices=notices,
            ),
            "orders": orders,
            "payment_method": payment_method,
        }
    elif intent == "payment":
        answer, payment_method = get_payment_response(request.query)
        return {
            "question": request.query,
            "intent": "payment",
            "answer": answer,
            "payment_method": payment_method,
        }
    else:
        answer = qa_chain.invoke({"question": request.query, "cart_items": request.cart_items})
        return {"question": request.query, "intent": intent, "answer": answer}
