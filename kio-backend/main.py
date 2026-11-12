import os
import re
import tempfile

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
    extract_menu,
    fix_stt_errors,
    normalize_text,
)
from ai.payment import get_payment_response
from ai.dialog import _HOT as _HOT_W, _ICE as _ICE_W
from ai.stt import transcribe as transcribe_audio
from ai.logging_utils import log_feedback, log_intent_query, log_interaction
from ai.order import (
    _is_noise_menu,
    _josa,
    apply_discount_menu_fallback,
    cart_answer,
    entities_to_orders,
    limit_by_stock,
    split_sold_out,
    validate_options,
)
from ai.cart_command import detect_cart_command, parse_cart
from ai.dialog import answer_slot, current_question, start_dialog
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

_last_recommended_menus: list[str] = []
_last_asked: list[str] = []      # 방금 가격·재료 등을 물어본 메뉴 ("그럼 그걸로 주세요"의 '그걸')
_pending_temp: list[str] = []    # "따뜻한 커피"처럼 종류를 고르기 전에 말한 온도 ('핫'/'아이스')
_RE_THAT_ONE = re.compile(r"그럼|그걸|그거|그것|거기|이걸|이거")

_DISCOUNT_QUESTION_PATTERN = re.compile(
    r"(\?|되나요|되나|돼요|되나여|가능해|가능한가|뭐야|뭐예요|뭔가요|얼마|무엇|알려줘)"
)

_RE_DISCOUNT_INFO = re.compile(
    normalize_text(r"(?:할인|혜택).{0,8}(?:뭐|무엇|뭘|어떤|무슨|있|알려|종류)|(?:뭐|어떤|무슨).{0,6}(?:할인|혜택)")
)
_RE_DISCOUNT_SPECIFIC = re.compile(normalize_text(r"kt|티멤버십|t멤버십|우주|cj|씨제이|쿠폰|바코드"))
_RE_POPULAR = re.compile(
    normalize_text(r"잘나가|잘팔|베스트|많이(?:팔|시켜|주문|찾)|인기(?:메뉴|있는|많은|가많|제일|가장)|가장인기|제일인기|대표메뉴|시그니처")
)


def _discount_info_answer() -> str:
    discounts = admin_db.get_discounts(active_only=True)
    if not discounts:
        return "지금은 진행 중인 할인이 없어요."
    lines = []
    for i, d in enumerate(discounts, 1):
        first = (d.get("description") or "").strip().split("\n")[0]
        lines.append(f"{i}. {d['name']}: {first}" if first else f"{i}. {d['name']}")
    return ("지금 받을 수 있는 할인이에요.\n" + "\n".join(lines) +
            "\n결제할 때 해당 수단을 선택하거나 '쿠폰 쓸게요'라고 말씀해 주세요.")


def _popular_answer(menus: list[dict]) -> tuple[str, list[str]]:
    by_name = {m["name"]: m for m in menus}
    top = [t for t in admin_db.get_analytics()["top_menus"]
           if t["name"] in by_name and not by_name[t["name"]]["sold_out"]][:3]
    if not top:
        return ("아직 집계된 판매 기록이 없어요. 원하시는 맛이나 온도를 말씀해 주시면 추천해 드릴게요.", [])
    lines = [f"{i}번 {t['name']} ({t['count']}잔 판매)" for i, t in enumerate(top, 1)]
    return ("최근 일주일 동안 가장 많이 팔린 메뉴예요.\n" + "\n".join(lines) +
            "\n번호로 말씀하시면 바로 담아드려요.", [t["name"] for t in top])

_RE_TEMP_QUESTION = re.compile(normalize_text(r"가능|되나|돼요|될까|되려나|있나|있어요|있을까|할수|\?"))
_RE_WANT_HOT = re.compile(normalize_text(r"따뜻|뜨겁|뜨거|핫|안차갑|안시원|차갑지않|덜차갑|미지근"))
_RE_WANT_ICE = re.compile(normalize_text(r"아이스|차갑|시원|얼음"))
_RE_ORDER_WORDS = re.compile(normalize_text(r"주세요|줘|주라|담아|할게|주문"))


def _temperature_answer(query: str, menus: list[dict]) -> str | None:
    qn = normalize_text(query)
    if not _RE_TEMP_QUESTION.search(qn) or _RE_ORDER_WORDS.search(qn):
        return None
    want = "HOT" if _RE_WANT_HOT.search(qn) else "ICE" if _RE_WANT_ICE.search(qn) else None
    name = extract_menu(query, [m["name"] for m in menus])
    if not want or not name:
        return None
    info = next((m for m in menus if m["name"] == name), None)
    temps = (info or {}).get("temps") or []
    if not temps:
        return None
    topic = _josa(name, "은", "는")
    if want in temps:
        return f"네, {topic} {'따뜻하게도' if want == 'HOT' else '아이스로도'} 주문할 수 있어요."
    only = "아이스" if "ICE" in temps else "따뜻한"
    return f"{topic} {only} 음료로만 주문할 수 있어요."


def _menu_words(name: str) -> list[str]:
    return [w for w in name.split() if len(w) >= 2]


def _resolve_by_recommended(query: str) -> dict | None:
    qn = normalize_text(query)
    cands = []
    for rec in _last_recommended_menus:
        base = rec.removeprefix("핫 ").removeprefix("아이스 ")
        if any(normalize_text(w) in qn for w in _menu_words(base)):
            cands.append(rec)
    if len(cands) != 1:
        return None
    return {
        "menu": cands[0],
        "quantity": extract_quantity(query),
        "attributes": extract_attributes(query),
        "options": extract_options_from_text(query),
        "option_details": extract_option_details(query),
        "packaging": extract_packaging(query),
        "needs_recommendation": False,
    }


def _resolve_last_asked(query: str) -> dict | None:
    """"카페라떼 얼마예요?" → "그럼 아이스로 하나 주세요": 방금 물어본 메뉴를 가리키는 말이면 그 메뉴로 받는다."""
    if len(_last_asked) != 1 or not _RE_THAT_ONE.search(query):
        return None
    menu = _last_asked[0]
    _last_asked.clear()
    return {
        "menu": menu, "quantity": extract_quantity(query), "attributes": extract_attributes(query),
        "options": extract_options_from_text(query), "option_details": extract_option_details(query),
        "packaging": extract_packaging(query), "needs_recommendation": False,
    }


def _ambiguous_menu_question(query: str, menus: list[dict]) -> tuple[str, list[str]] | None:
    qn = normalize_text(query)
    best: tuple[str, list[str]] | None = None
    for word in {w for m in menus for w in _menu_words(m["name"])}:
        if normalize_text(word) not in qn:
            continue
        names = [m["name"] for m in menus if not m["sold_out"] and word in _menu_words(m["name"])]
        if len(names) >= 2 and (best is None or len(names) < len(best[1])):
            best = (word, names[:4])
    if not best:
        return None
    word, names = best
    lines = "\n".join(f"{i}번 {n}" for i, n in enumerate(names, 1))
    return f"'{word}'가 들어간 메뉴가 여러 개예요. 어느 걸로 할까요?\n{lines}\n번호로 말씀해 주세요.", names


_CATEGORY_WORDS = (  # 어르신이 메뉴 이름 대신 종류로 말하는 경우: (정규식, 메뉴 카테고리들, 부르는 말)
    (re.compile(r"커피"), ("커피",), "커피"),
    (re.compile(r"차(?![가-힣])|티(?![가-힣])"), ("티",), "차"),
    (re.compile(r"주스|쥬스|과일\s*음료"), ("주스",), "주스"),
    (re.compile(r"에이드"), ("에이드",), "에이드"),
    (re.compile(r"스무디"), ("스무디",), "스무디"),
)


def _category_question(query: str, menus: list[dict]) -> tuple[str, list[str]] | None:
    """"커피 하나 주세요"처럼 종류만 말했을 때 그 종류의 메뉴를 보여 주고 고르게 한다."""
    for rx, cats, label in _CATEGORY_WORDS:
        if not rx.search(query):
            continue
        names = [m["name"] for m in menus if m["category"] in cats and not m["sold_out"]]
        if not names:
            return None
        shown = names[:4]
        lines = "\n".join(f"{i}번 {n}" for i, n in enumerate(shown, 1))
        more = " 그 밖의 메뉴는 화면에서 볼 수 있어요." if len(names) > len(shown) else ""
        return f"{label}는 이런 메뉴가 있어요. 어느 걸로 드릴까요?\n{lines}\n번호나 이름으로 말씀해 주세요.{more}", shown
    return None


def _temp_prefix(query: str) -> str | None:
    t = normalize_text(query)
    hot, ice = bool(_HOT_W.search(t)), bool(_ICE_W.search(t))
    return "핫" if hot and not ice else "아이스" if ice and not hot else None


def _resolve_ordinal_order(query: str) -> dict | None:
    ordinal = extract_ordinal(query)
    if ordinal and 1 <= ordinal <= len(_last_recommended_menus):
        chosen_menu = _last_recommended_menus[ordinal - 1]
        if _pending_temp and not _temp_prefix(query) and not chosen_menu.startswith(("핫 ", "아이스 ")):
            chosen_menu = f"{_pending_temp[0]} {chosen_menu}"  # 목록을 보여 주기 전에 말한 온도를 이어 간다
        _pending_temp.clear()
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
    alternatives = {}
    for name in sold_out:
        alts = find_alternatives(name, menus)
        if alts:
            alternatives[name] = alts
    if alternatives:
        _last_recommended_menus[:] = next(iter(alternatives.values()))
    return alternatives


def _recommend(query: str):
    by_rule = recommend_by_conditions(query, admin_db.get_menus())
    if by_rule is not None:
        return by_rule
    return recommend_chain.invoke(query)


def _cart_quantities(cart_items: list[str]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for line in parse_cart(cart_items):
        totals[line["menu"]] = totals.get(line["menu"], 0) + line["quantity"]
    return totals


def _order_response(
    question: str,
    orders: list[dict],
    named: list[dict],
    sold_out: list[str],
    menus: list[dict] | None = None,
    notices: list[str] | None = None,
) -> dict:
    alternatives = _alternatives_map(sold_out, menus or [])
    return {
        "question": question,
        "intent": "order",
        "answer": cart_answer(named, sold_out, alternatives=alternatives, notices=notices),
        "orders": orders,
        "sold_out": sold_out,
        "alternatives": alternatives,
    }


class QueryRequest(BaseModel):
    query: str
    cart_items: list[str] = []
    dialog: dict | None = None  # 열려 있는 옵션 되묻기 대화 상태 (프론트가 되돌려 보냄)


def _dialog_response(question: str, res: dict, **extra) -> dict:
    return {
        "question": question,
        "intent": "dialog",
        "answer": res["answer"],
        "orders": res["orders"],
        "dialog": res["state"],
        "go_payment": res["go_payment"],
        "memo": res.get("memo"),
        **extra,
    }


_RE_PAY_NOW = re.compile(r"결제|계산|카드요|카드로|카드\s*(?:할게|줄게)|페이로|페이\s*(?:할게|요)")
_RE_PAY_NOW_NEG = re.compile(r"얼마|어떻게|되나요|돼요|가능|할인|쿠폰|말고|아니")


def _wants_pay_now(query: str) -> bool:
    return bool(_RE_PAY_NOW.search(query)) and not _RE_PAY_NOW_NEG.search(query)


def _order_and_pay_now(question: str, orders: list[dict], named: list[dict], sold_out: list[str],
                       menus: list[dict], notices: list[str]) -> dict:
    _, method = get_payment_response(question)
    label = {"card": "카드", "kakao": "카카오페이", "naver": "네이버페이"}.get(method or "", "")
    suffix = f" {label}로 결제 화면으로 이동합니다." if label else " 결제 화면으로 이동합니다."
    alternatives = _alternatives_map(sold_out, menus)
    return {
        "question": question,
        "intent": "order_and_pay",
        "answer": cart_answer(named, sold_out, pay_suffix=suffix, alternatives=alternatives, notices=notices),
        "orders": orders,
        "payment_method": method,
        "sold_out": sold_out,
        "alternatives": alternatives,
    }


@app.get("/")
def root():
    return {"msg": "hello"}


@app.post("/api/stt")
async def speech_to_text(file: UploadFile = File(...)):
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

_TTS_CACHE: dict[str, bytes] = {}
TTS_VOICE = os.getenv("TTS_VOICE", "ko-KR-SunHiNeural")
TTS_RATE = os.getenv("TTS_RATE", "-8%")


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=400)


@app.post("/api/tts")
async def text_to_speech(body: TTSRequest):
    text = body.text.strip()
    if text in _TTS_CACHE:
        return Response(_TTS_CACHE[text], media_type="audio/mpeg")
    try:
        import edge_tts
    except ImportError:
        raise HTTPException(status_code=503, detail="edge-tts가 설치되지 않았습니다.")
    try:
        chunks = [c["data"] async for c in edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE).stream()
                  if c["type"] == "audio"]
    except Exception:
        raise HTTPException(status_code=503, detail="음성 합성 서버에 연결하지 못했습니다.")
    if not chunks:
        raise HTTPException(status_code=503, detail="음성을 만들지 못했습니다.")
    audio = b"".join(chunks)
    if len(_TTS_CACHE) < 200:
        _TTS_CACHE[text] = audio
    return Response(audio, media_type="audio/mpeg")


class FeedbackRequest(BaseModel):
    query: str
    answer: str = ""
    intent: str | None = None


@app.post("/api/feedback", status_code=204)
def feedback(body: FeedbackRequest):
    log_feedback(body.query[:300], body.answer[:500], body.intent)


@app.post("/api/ask")
async def ask_intent(request: QueryRequest):
    raw = request.query
    result = await _handle_ask(request)
    log_interaction(raw, request.cart_items, result)
    return result


async def _handle_ask(request: QueryRequest) -> dict:
    """질문·추천 같은 곁가지에 답할 때도 열려 있던 되묻기 대화는 잃지 않고, 하던 질문을 이어서 묻는다."""
    dialog = request.dialog
    result = await _handle_ask_inner(request)
    if (dialog and result.get("intent") in ("qa", "recommend") and result.get("dialog") is None):
        again = current_question(dialog)
        if again:
            result["dialog"] = dialog
            result["answer"] = f"{result.get('answer', '')} {again}".strip()
    return result


async def _handle_ask_inner(request: QueryRequest) -> dict:
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문이 비어있습니다.")

    request.query = fix_stt_errors(request.query)
    all_menus = admin_db.get_menus()

    if request.dialog:
        slot_res = answer_slot(request.dialog, request.query, all_menus, request.cart_items, detect_cart_command)
        if slot_res is not None:
            return _dialog_response(request.query, slot_res)

    command = detect_cart_command(request.query, request.cart_items, all_menus)
    if command:
        return {"question": request.query, **command}

    qn = normalize_text(request.query)
    if _RE_POPULAR.search(qn):
        answer, popular = _popular_answer(all_menus)
        _last_recommended_menus[:] = popular
        return {"question": request.query, "intent": "recommend", "answer": answer, "recommended_menus": popular}
    if (_RE_DISCOUNT_INFO.search(qn) and not _RE_DISCOUNT_SPECIFIC.search(qn)
            and not extract_menu(request.query, [m["name"] for m in all_menus])):
        return {"question": request.query, "intent": "qa", "answer": _discount_info_answer()}

    temp_answer = _temperature_answer(request.query, all_menus)
    if temp_answer:
        return {"question": request.query, "intent": "qa", "answer": temp_answer}

    intent = fast_classify(request.query, [m["name"] for m in all_menus]) or classify_intent(request.query)
    log_intent_query(request.query, intent)

    if intent == "order":
        menus = all_menus
        menu_names = [m["name"] for m in menus]
        sold_out_names = {m["name"] for m in menus if m["sold_out"]}

        entities = extract_multi_order(request.query, menu_names)

        if all(_is_noise_menu(e.get("menu")) for e in entities):
            ordinal_entity = (_resolve_ordinal_order(request.query) or _resolve_by_recommended(request.query)
                              or _resolve_last_asked(request.query))
            ambiguous = None if ordinal_entity else _ambiguous_menu_question(request.query, menus)
            if ordinal_entity:
                entities = [ordinal_entity]
            elif ambiguous:
                _pending_temp[:] = [x for x in [_temp_prefix(request.query)] if x]
                _last_recommended_menus[:] = ambiguous[1]
                return {"question": request.query, "intent": "recommend", "answer": ambiguous[0],
                        "recommended_menus": ambiguous[1]}
            elif _category_question(request.query, menus):
                answer, shown = _category_question(request.query, menus)
                _pending_temp[:] = [x for x in [_temp_prefix(request.query)] if x]
                _last_recommended_menus[:] = shown
                return {"question": request.query, "intent": "recommend", "answer": answer,
                        "recommended_menus": shown}
            elif _DISCOUNT_QUESTION_PATTERN.search(request.query):
                answer = qa_chain.invoke({"question": request.query, "cart_items": request.cart_items})
                return {"question": request.query, "intent": "qa", "answer": answer}
            elif extract_attributes(request.query) and all(
                    _is_noise_menu(e.get("menu"))
                    for e in apply_discount_menu_fallback(entities, request.query, menu_names)):
                # "시원한 거 하나 주세요", "달달한 걸로"처럼 메뉴 없이 취향만 말하면 추천으로 이어 간다
                result = _recommend(request.query)
                _last_recommended_menus[:] = result.menus
                return {"question": request.query, "intent": "recommend", "answer": result.answer,
                        "recommended_menus": result.menus}
            else:
                entities = apply_discount_menu_fallback(entities, request.query, menu_names)

        orders_all = entities_to_orders(entities)
        orders, sold_out = split_sold_out(orders_all, sold_out_names)
        orders, stock_notices = limit_by_stock(orders, menus, _cart_quantities(request.cart_items))
        orders, notices = validate_options(orders, menus)
        named = [o for o in orders if o["menu"]]
        if named and _wants_pay_now(request.query):
            # "아아 두 잔 결제", "라떼 하나 카드요"처럼 주문과 결제를 한 번에 말하면 되묻지 않고 바로 결제로 간다
            return _order_and_pay_now(request.query, orders, named, sold_out, menus, stock_notices + notices)
        started = start_dialog(named, menus) if named else None
        if started is not None:
            # 온도를 되물을 거라 '아이스로 담았어요' 안내는 뺀다
            keep = [n for n in stock_notices + notices if not n.startswith("온도를 말씀하지 않으셔서")]
            if sold_out or keep:
                started["answer"] = cart_answer(
                    [], sold_out, alternatives=_alternatives_map(sold_out, menus), notices=keep
                ) + " " + started["answer"]
            return _dialog_response(request.query, started, sold_out=sold_out)
        notices = stock_notices + notices
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
        orders, stock_notices = limit_by_stock(orders, menus, _cart_quantities(request.cart_items))
        orders, notices = validate_options(orders, menus)
        notices = stock_notices + notices
        named = [o for o in orders if o["menu"]]
        _, payment_method = get_payment_response(request.query)

        if not payment_method:
            return _order_response(request.query, orders, named, sold_out, menus, notices)

        if (sold_out or stock_notices) and not named:
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
        mentioned = extract_menu(request.query, [m["name"] for m in all_menus])
        _last_asked[:] = [mentioned] if mentioned else []
        answer = qa_chain.invoke({"question": request.query, "cart_items": request.cart_items})
        return {"question": request.query, "intent": intent, "answer": answer}
