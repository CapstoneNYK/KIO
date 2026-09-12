import os
import re
import tempfile

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai.recommend import qa_chain, recommend_chain
from ai.intent import classify_intent
from ai.entity import (
    extract_multi_order,
    extract_ordinal,
    extract_quantity,
    extract_attributes,
    extract_options_from_text,
)
from ai.payment import get_payment_response
from ai.discount import get_discount_tip
from ai.stt import transcribe as transcribe_audio
from ai.logging_utils import log_intent_query
from app.ocr.router import router as ocr_router
from app.ocr.db import get_all_menu_texts, get_all_discount_texts
from app.coupon.router import router as coupon_router

load_dotenv()

app = FastAPI()

# FRONTEND_URL에 콤마로 여러 주소를 넣을 수 있게 하고(.env: FRONTEND_URL=http://localhost:5173,http://192.168.0.17:5173),
# 추가로 같은 와이파이(192.168.x.x)나 Tailscale(100.x.x.x)로 접속하는 흔한 케이스는
# 정규식으로 한 번에 허용한다. PC를 서버로 쓰면서 다른 기기(노트북 등)로 접속할 때마다
# IP가 바뀌어서 매번 .env를 고쳐야 하는 번거로움을 줄이기 위함.
_frontend_urls = [u.strip() for u in os.getenv("FRONTEND_URL", "http://localhost:5173").split(",") if u.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_frontend_urls,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|100\.\d{1,3}\.\d{1,3}\.\d{1,3}):5173",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr_router)
app.include_router(coupon_router)

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
            "needs_recommendation": False,
        }
    return None


# 할인 수단 언급 + 메뉴 미추출(또는 단음절 오인식) 시 할인 대상 메뉴로 보완할 때 쓰는 표.
# (요청마다 새로 만들 필요 없는 고정 데이터라 모듈 레벨로 뺐다.)
_DISCOUNT_MENU_MAP = {
    "T멤버십": ("아메리카노", None),   # None = 온도 그대로 (ICE/HOT 무관)
    "tmembership": ("아메리카노", None),
}


def _is_noise_menu(menu: str | None) -> bool:
    """메뉴명이 비어있거나, 할인 키워드 앞글자(T/KT 등)를 잘못 메뉴로 인식한 노이즈인지 판단."""
    if not menu:
        return True
    cleaned = menu.strip()
    if len(cleaned) <= 2:
        return True
    if cleaned.upper() in ("T", "KT", "CJ", "SKT"):
        return True
    return False


def _entities_to_orders(entities: list[dict]) -> list[dict]:
    """entity 추출 결과(menu/attributes/quantity/options/needs_recommendation)를
    프론트에 내려줄 orders 형식으로 변환한다. "아이스 "/"핫 " 접두어가 붙어 있으면
    분리해서 temperature 필드로 뺀다. order/order_and_pay 두 분기에서 동일하게 써서
    하나로 뽑았다."""
    orders = []
    for entity in entities:
        base_menu = None
        temperature = "ICE"
        if entity["menu"]:
            raw = entity["menu"]
            if raw.startswith("아이스 "):
                base_menu = raw[4:]
                temperature = "ICE"
            elif raw.startswith("핫 "):
                base_menu = raw[2:]
                temperature = "HOT"
            else:
                base_menu = raw
                temperature = "HOT" if "hot" in entity["attributes"] else "ICE"
        orders.append({
            "menu": base_menu,
            "temperature": temperature,
            "quantity": entity["quantity"],
            "options": entity.get("options", []),
            "needs_recommendation": entity["needs_recommendation"],
        })
    return orders


def _format_items(named: list[dict]) -> str:
    return ", ".join(
        f"{'아이스' if o['temperature'] == 'ICE' else '따뜻한'} {o['menu']}"
        for o in named
    )


def _order_response(question: str, orders: list[dict], named: list[dict]) -> dict:
    """"장바구니에 담았습니다" 형태의 일반 주문 응답을 만든다.
    order 분기와, order_and_pay인데 실제로는 결제수단이 없어서 order로 강등되는
    경우에서 공용으로 쓴다."""
    answer = f"{_format_items(named)}을(를) 장바구니에 담았습니다." if named else "어떤 메뉴를 주문하시겠어요?"
    discount_tip = get_discount_tip(get_all_discount_texts()) if named else None
    return {
        "question": question,
        "intent": "order",
        "answer": answer,
        "orders": orders,
        "discount_tip": discount_tip,
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

    result = recommend_chain.invoke(request.query)
    _last_recommended_menus[:] = result.menus
    return {"question": request.query, "answer": result.answer, "recommended_menus": result.menus}


@app.post("/api/ask")
async def ask_intent(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문이 비어있습니다.")

    intent = classify_intent(request.query)
    # 실사용 발화+예측 의도를 누적 기록 -> 나중에 검토 후 파인튜닝 데이터로 활용
    log_intent_query(request.query, intent)

    if intent == "order":
        ocr_menus = get_all_menu_texts()
        entities = extract_multi_order(request.query, ocr_menus)

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
                q_norm = request.query.replace(" ", "")
                for keyword, (menu, temp) in _DISCOUNT_MENU_MAP.items():
                    if keyword.replace(" ", "") in q_norm:
                        resolved_temp = temp if temp else "ICE"
                        entities = [{"menu": menu, "quantity": 1, "temperature": resolved_temp,
                                     "options": [], "attributes": [], "needs_recommendation": False}]
                        break

        orders = _entities_to_orders(entities)
        named = [o for o in orders if o["menu"]]
        return _order_response(request.query, orders, named)
    elif intent == "coupon":
        return {
            "question": request.query,
            "intent": "coupon",
            "answer": "쿠폰 바코드를 카메라로 스캔해볼게요!",
        }
    elif intent == "recommend":
        result = recommend_chain.invoke(request.query)
        _last_recommended_menus[:] = result.menus
        return {
            "question": request.query,
            "intent": intent,
            "answer": result.answer,
            "recommended_menus": result.menus,
        }
    elif intent == "order_and_pay":
        ocr_menus = get_all_menu_texts()
        entities = extract_multi_order(request.query, ocr_menus)

        if all(not e.get("menu") for e in entities):
            ordinal_entity = _resolve_ordinal_order(request.query)
            if ordinal_entity:
                entities = [ordinal_entity]

        orders = _entities_to_orders(entities)
        named = [o for o in orders if o["menu"]]
        _, payment_method = get_payment_response(request.query)

        if not payment_method:
            # 결제수단이 실제로 언급되지 않았는데도 로컬 LLM이 order_and_pay로
            # 잘못 분류하는 경우가 있다("결제수단 언급 없음"이 order_and_pay가 될
            # 조건이 아닌데도 종종 발생). 결제 화면으로 강제 이동시키지 않고
            # 그냥 주문(order)처럼 장바구니에만 담는다.
            return _order_response(request.query, orders, named)

        if named:
            method_label = {
                "card": "카드", "kakao": "카카오페이", "naver": "네이버페이",
                "appcard": "앱카드", "voucher": "모바일상품권", "giftcard": "기프트카드",
                "kt": "KT VIP", "tmembership": "T멤버십", "cjone": "CJ ONE", "uzu": "T우주",
            }.get(payment_method or "", "")
            suffix = f" {method_label}로 결제 화면으로 이동합니다." if method_label else " 결제 화면으로 이동합니다."
            answer = f"{_format_items(named)}을(를) 장바구니에 담고{suffix}"
        else:
            answer = "어떤 메뉴를 주문하시겠어요?"

        return {
            "question": request.query,
            "intent": "order_and_pay",
            "answer": answer,
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
