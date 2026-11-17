import os
import re
import tempfile
import time
import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # ai.llm·ai.stt·app.admin.auth 가 import 시점에 환경변수를 읽으므로 다른 import 보다 먼저 불러온다

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai.recommend import RecommendOutput, qa_chain, recommend_chain
from ai.intent import classify_intent
from ai.fast_intent import fast_classify
from ai.entity import (
    MULTI_SPLIT_PATTERN,
    extract_multi_order,
    extract_ordinal_segments,
    extract_quantity,
    extract_attributes,
    extract_options_from_text,
    extract_option_details,
    extract_packaging,
    extract_menu,
    fix_stt_errors,
    normalize_text,
)
from ai.menu_match import alias_answer, ingredient_answer, resolve_owned_aliases
from ai.payment import extract_payment_method, get_payment_response, payment_label
from ai.stt import transcribe as transcribe_audio, warmup as warmup_stt
from ai.llm import warmup as warmup_llm
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
from ai.dialog import _HOT as _HOT_W, _ICE as _ICE_W, _refers_to, answer_slot, current_question, start_dialog
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

def _warmup_models() -> None:
    t0 = time.perf_counter()
    try:
        warmup_stt()
    except Exception as e:
        print("[warmup] STT 워밍업 실패:", e)
    warmup_llm()
    print(f"[warmup] 모델 준비 완료 {(time.perf_counter() - t0) * 1000:.0f}ms")


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    await asyncio.to_thread(_warmup_models)  # 워밍업이 끝난 뒤부터 요청을 받는다
    yield


app = FastAPI(lifespan=_lifespan)

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
_RE_AFFIRM = re.compile(r"^(?:네|넵|예|응|어|음|그래|그래요|좋아|좋아요|그럼|맞아|맞아요|그걸로|그거|그걸로요|그걸로할게|그걸로주세요|그걸로줘)[.!~요]*$")
_RE_THAT_ONE = re.compile(r"그럼|그걸|그거|그것|거기|이걸|이거|저걸|저거|그걸루")

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


def _resolve_single_recommended(query: str) -> dict | None:
    """방금 메뉴를 하나만 권했다면 "그걸로 두 잔 줘", "어 그거 하나"는 그 메뉴를 가리킨다."""
    if len(_last_recommended_menus) != 1 or not _RE_THAT_ONE.search(query):
        return None
    menu = _last_recommended_menus[0]
    _last_recommended_menus.clear()  # 한 번 주문에 쓰면 비워서, 나중의 "그거"가 옛 추천을 다시 주문하지 않게 한다
    return {
        "menu": menu, "quantity": extract_quantity(query), "attributes": extract_attributes(query),
        "options": extract_options_from_text(query), "option_details": extract_option_details(query),
        "packaging": extract_packaging(query), "needs_recommendation": False,
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


_CATEGORY_ASK = re.compile(r"종류|뭐\s*(?:가\s*)?있|뭐뭐|어떤\s*(?:게|거|메뉴)|무슨\s*(?:게|거|메뉴)")


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


_RE_ALL_SHOWN = re.compile(r"[둘셋넷]\s*(?:다|모두|전부)|전부|모두|각각|다\s*(?:주세요|줘|주라|할게|먹)")


_RE_EXPLICIT_QTY = re.compile(r"\d+\s*[잔개컵]|(?:한|두|세|네|다섯|여섯)\s*[잔개컵]|하나|둘(?!\s*(?:다|모두|전부))|셋|넷")
_RE_SHARED_QTY = re.compile(r"씩|각각|[둘셋넷]\s*(?:다|모두|전부)|모두|전부")


def _explicit_qty(seg: str) -> int | None:
    return extract_quantity(seg) if _RE_EXPLICIT_QTY.search(seg) else None


_RE_REQUEST_CUE = re.compile(
    r"저지방|무지방|두유|오트|귀리|아몬드|우유|덜\s*달|달게|달지|시럽|설탕|얼음|휘핑|크림|미지근|싱겁|넣지|"
    r"빼\s*(?:줘|주세요|달라|고)|많이|적게|조금만|따로|디카페인|빨대|리필|알레르기|펌프|펄|타피오카|젤리")
_RE_REQUEST_NOT = re.compile(r"더\s*(?:주세요|줘|추가)|하나\s*더|한\s*잔\s*더|결제|계산|취소|삭제|지워|얼마|가격|뭐|"
                             r"있나요|있어요|있어\?|되나요|돼요|가능|알려")


def _cart_label(line: str) -> str:
    """장바구니 줄("아이스 딸기 라떼 ×2 (시럽 적게)")에서 음료 이름만: "아이스 딸기 라떼"."""
    return re.split(r"\s+×\d+|\s+\(", line, maxsplit=1)[0].strip()


_RE_DEICTIC = re.compile(r"여기|거기|이거|그거|이것|그것|방금|이\s*음료|이\s*메뉴")


def _memo_menu(query: str, cart_items: list[str], dialog: dict | None = None) -> str | None:
    """요청사항이 어느 음료에 대한 것인지. 주문서에 "[아이스 딸기 라떼] 우유는 저지방으로"처럼 붙인다.
    음료를 말했으면 그 음료, 말하지 않았어도 장바구니에 한 종류뿐이면 그 음료, 여럿이면 알 수 없어서 None(주문 전체)."""
    labels = list(dict.fromkeys(_cart_label(line) for line in cart_items if line.strip()))
    if not labels:
        return None
    qn = normalize_text(query)
    named = []
    for lb in labels:
        menu = re.sub(r"^(?:아이스|따뜻한)\s*", "", lb)
        if normalize_text(menu) in qn or _refers_to(query, menu):  # "아메리카노에"처럼 조사가 붙어도 찾는다
            named.append(lb)
    if named:
        return ", ".join(named)
    if len(labels) == 1:
        return labels[0]
    last = ((dialog or {}).get("last") or [None])[-1]  # "여기에 시럽 넣어줘" — 방금 담은 음료
    if last and last.get("menu") and _RE_DEICTIC.search(query):
        return ("아이스 " if last.get("temperature") == "ICE" else "따뜻한 ") + last["menu"]
    return None


def _memo_request(query: str, menus: list[dict], cart_items: list[str], dialog: dict | None = None) -> dict | None:
    """담아 둔 메뉴에 대한 추가 요청("딸기라떼 우유는 저지방으로", "카페라떼는 디카페인으로")은 새 주문이 아니라 요청사항 메모로 적는다."""
    if not cart_items or not _RE_REQUEST_CUE.search(query) or _RE_REQUEST_NOT.search(query):
        return None
    if extract_option_details(query) and "펌프" not in query:  # 샷 추가 같은 정식 옵션은 기존 처리(시럽 "두 펌프"는 옵션으로 못 담아서 요청사항으로)
        return None
    qn = normalize_text(query)
    cart_text = normalize_text(" ".join(cart_items))
    named = [m["name"] for m in menus if normalize_text(m["name"]) in qn]
    if named and not any(normalize_text(n) in cart_text for n in named):
        return None  # 아직 안 담은 메뉴를 말했으면 새 주문이다
    memo = re.sub(r"^(?:근데|그리고|아\s*참|참|그런데)\s*", "", re.sub(r"\s+", " ", query).strip()).rstrip("?.! ")[:60]
    trimmed = re.sub(r"\s*(?:달라고|해달라고)?\s*(?:해\s*줄래|해\s*주세요|해\s*줘|해\s*주라|부탁(?:해요|드려요|해)?)$", "", memo).strip()
    memo = trimmed if len(trimmed) >= 2 else memo  # "펄 많이 달라고 해줄래" -> "펄 많이"
    return {"question": query, "intent": "qa", "answer": f"'{memo}' 요청사항으로 적어 둘게요.", "memo": memo,
            "memo_menu": _memo_menu(query, cart_items, dialog)}


def _resolve_ordinal_orders(query: str) -> list[dict]:
    """추천 목록에서 번호로 고른 주문. "2번 하나랑 3번 두 개"처럼 여러 번호는 번호마다 수량을 따로 읽는다."""
    picks = [(n, seg) for n, seg in extract_ordinal_segments(query) if 1 <= n <= len(_last_recommended_menus)]
    if not picks and len(_last_recommended_menus) >= 2 and _RE_ALL_SHOWN.search(query):
        # "둘 다 한 잔씩", "전부 주세요": 방금 보여 준 목록을 모두 고른 것이다
        picks = [(n, query) for n in range(1, len(_last_recommended_menus) + 1)]
    if not picks:
        return []
    multi = len(picks) > 1 and picks[0][1] != query
    # "1번 2번 둘 다 두 잔씩"처럼 수량을 한 번만 말했으면 고른 메뉴 모두에 같은 수량을 준다
    shared = _explicit_qty(picks[-1][1]) if multi and _RE_SHARED_QTY.search(query) else None
    temp = _pending_temp[0] if _pending_temp and not _temp_prefix(query) else None
    _pending_temp.clear()
    entities = []
    for n, seg in picks:
        menu = _last_recommended_menus[n - 1]
        if temp and not menu.startswith(("핫 ", "아이스 ")):
            menu = f"{temp} {menu}"  # 목록을 보여 주기 전에 말한 온도를 이어 간다
        entities.append({
            "menu": menu,
            "quantity": ((_explicit_qty(seg) or shared or 1) if multi else extract_quantity(query)),
            "attributes": extract_attributes(query),
            "options": extract_options_from_text(query),
            "option_details": extract_option_details(query),
            "packaging": extract_packaging(query),
            "needs_recommendation": False,
        })
    return entities


def _mix_ordinal_with_named(query: str, entities: list[dict], menu_names: list[str]) -> list[dict]:
    """"1번으로 따뜻하게 두 잔이랑 레몬에이드 한 잔"처럼 추천 목록의 번호와 메뉴 이름을 함께 말한 주문.
    번호 부분은 추천 목록에서, 이름 부분은 메뉴 이름으로 따로 읽어 합친다(이름만 읽으면 번호 부분이 빠진다)."""
    if not _last_recommended_menus or all(_is_noise_menu(e.get("menu")) for e in entities):
        return entities  # 메뉴 이름이 하나도 없으면 번호만 말한 주문이라 기존 처리로 둔다
    parts = [p.strip() for p in MULTI_SPLIT_PATTERN.split(fix_stt_errors(query)) if p.strip()]
    if len(parts) < 2:
        return entities
    merged: list[dict] = []
    ordinal_parts = 0
    for part in parts:
        if extract_menu(part, menu_names):
            merged += [e for e in extract_multi_order(part, menu_names) if not _is_noise_menu(e.get("menu"))]
            continue
        picked = _resolve_ordinal_orders(part)
        if picked:
            ordinal_parts += 1
            merged += picked
    return merged if ordinal_parts and merged else entities


def _alternatives_map(sold_out: list[str], menus: list[dict]) -> dict[str, list[str]]:
    alternatives = {}
    for name in sold_out:
        alts = find_alternatives(name, menus)
        if alts:
            alternatives[name] = alts
    if alternatives:
        _last_recommended_menus[:] = next(iter(alternatives.values()))
    return alternatives


_LLM_FAIL_ANSWER = "지금은 답변을 준비하지 못했어요. 다시 한 번 말씀해 주세요."


def _recommend(query: str):
    menus = admin_db.get_menus()
    by_rule = recommend_by_conditions(query, menus)
    if by_rule is not None:
        return by_rule
    try:
        result = recommend_chain.invoke(query)
    except Exception as e:  # Ollama 가 꺼져 있거나 응답이 늦을 때도 키오스크가 멈추지 않게 한다
        print("추천 오류:", e)
        return RecommendOutput(answer=_LLM_FAIL_ANSWER, menus=[])
    # LLM 이 메뉴판에 없는 이름을 지어내면 '1번 주세요'로 없는 메뉴가 담기므로 걸러 낸다
    names = {m["name"] for m in menus}
    result.menus = [n for n in result.menus if n.removeprefix("핫 ").removeprefix("아이스 ") in names]
    if result.menus:  # LLM 의 "메뉴 - 맛" 목록은 기계 같아서, 고른 메뉴만 받아 문장은 우리가 만든다
        result.answer = _recommend_answer(result.menus, menus)
    return result


def _recommend_answer(picked: list[str], menus: list[dict]) -> str:
    by_name = {m["name"]: m for m in menus}
    lines = []
    for i, name in enumerate(picked, 1):
        tags = by_name.get(name.removeprefix("핫 ").removeprefix("아이스 "), {}).get("tags") or []
        lines.append(f"{i}번 {name}" + (f" ({', '.join(tags[:3])})" if tags else ""))
    return "이런 메뉴는 어떠세요?\n" + "\n".join(lines) + "\n마음에 드는 걸 번호나 이름으로 말씀해 주세요."


def _qa_answer(query: str, cart_items: list[str]) -> str:
    try:
        return qa_chain.invoke({"question": query, "cart_items": cart_items})
    except Exception as e:
        print("안내 답변 오류:", e)
        return _LLM_FAIL_ANSWER


def _cart_quantities(cart_items: list[str]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for line in parse_cart(cart_items):
        totals[line["menu"]] = totals.get(line["menu"], 0) + line["quantity"]
    return totals


def _prepare_orders(entities: list[dict], menus: list[dict], cart_items: list[str]):
    """말에서 뽑은 주문을 품절·재고·옵션 규칙에 맞춘다. (주문들, 메뉴가 있는 주문들, 품절 메뉴, 재고 안내, 옵션 안내)"""
    sold_out_names = {m["name"] for m in menus if m["sold_out"]}
    orders, sold_out = split_sold_out(entities_to_orders(entities), sold_out_names)
    orders, stock_notices = limit_by_stock(orders, menus, _cart_quantities(cart_items))
    orders, notices = validate_options(orders, menus)
    named = [o for o in orders if o["menu"]]
    return orders, named, sold_out, stock_notices, notices


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
        # "카드 결제할게요"처럼 되묻는 중에 결제 수단까지 말했으면 결제 화면에서 그 수단을 강조한다
        "payment_method": extract_payment_method(question) if res["go_payment"] else None,
        "memo": res.get("memo"),
        **extra,
    }


_RE_PAY_NOW = re.compile(r"결제|계산|카드요|카드로|카드\s*(?:할게|줄게)|페이로|페이\s*(?:할게|요)")
_RE_PAY_NOW_NEG = re.compile(r"얼마|어떻게|되나요|돼요|가능|할인|쿠폰|말고|아니")


def _wants_pay_now(query: str) -> bool:
    return bool(_RE_PAY_NOW.search(query)) and not _RE_PAY_NOW_NEG.search(query)


def _order_and_pay_now(question: str, orders: list[dict], named: list[dict], sold_out: list[str],
                       menus: list[dict], notices: list[str]) -> dict:
    method = extract_payment_method(question)
    label = payment_label(method)
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


_TTS_CACHE: dict[str, bytes] = {}
TTS_VOICE = os.getenv("TTS_VOICE", "ko-KR-SunHiNeural")
TTS_RATE = os.getenv("TTS_RATE", "+8%")


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
    request.query = resolve_owned_aliases(request.query, all_menus, _last_recommended_menus)  # 이미 권한 "버블티" -> "흑당버블티"
    if len(_last_recommended_menus) == 1 and not request.dialog and _RE_AFFIRM.match(normalize_text(request.query)):
        request.query = f"{_last_recommended_menus[0]} 하나 주세요"  # 하나만 권한 뒤 "응"·"그걸로" 하고 답하면 그 메뉴를 주문한다
        _last_recommended_menus.clear()

    if request.dialog:
        slot_res = answer_slot(request.dialog, request.query, all_menus, request.cart_items, detect_cart_command)
        if slot_res is not None:
            resp = _dialog_response(request.query, slot_res)
            if resp.get("memo"):
                resp["memo_menu"] = _memo_menu(request.query, request.cart_items, request.dialog)
            return resp

    command = detect_cart_command(request.query, request.cart_items, all_menus)
    if command:
        return {"question": request.query, **command}

    memo_request = _memo_request(request.query, all_menus, request.cart_items, request.dialog)
    if memo_request:
        return memo_request

    qn = normalize_text(request.query)
    if _RE_POPULAR.search(qn):
        answer, popular = _popular_answer(all_menus)
        _last_recommended_menus[:] = popular
        return {"question": request.query, "intent": "recommend", "answer": answer, "recommended_menus": popular}
    if (_RE_DISCOUNT_INFO.search(qn) and not _RE_DISCOUNT_SPECIFIC.search(qn)
            and not extract_menu(request.query, [m["name"] for m in all_menus])):
        return {"question": request.query, "intent": "qa", "answer": _discount_info_answer()}

    if _CATEGORY_ASK.search(qn) and not extract_menu(request.query, [m["name"] for m in all_menus]):
        category = _category_question(request.query, all_menus)  # "스무디 종류 뭐 있어?" — LLM 없이 목록으로 답한다
        if category:
            answer, shown = category
            _pending_temp[:] = [x for x in [_temp_prefix(request.query)] if x]
            _last_recommended_menus[:] = shown
            return {"question": request.query, "intent": "recommend", "answer": answer, "recommended_menus": shown}

    for matched in (alias_answer(request.query, all_menus), ingredient_answer(request.query, all_menus)):
        if matched:  # 메뉴판에 없는 이름 -> 비슷한 메뉴 / 재료·과일이 들어간 메뉴 목록
            _last_recommended_menus[:] = matched[1]
            return {"question": request.query, "intent": "recommend", "answer": matched[0], "recommended_menus": matched[1]}

    temp_answer = _temperature_answer(request.query, all_menus)
    if temp_answer:
        return {"question": request.query, "intent": "qa", "answer": temp_answer}

    intent = fast_classify(request.query, [m["name"] for m in all_menus]) or classify_intent(request.query)
    log_intent_query(request.query, intent)

    if intent == "order":
        menus = all_menus
        menu_names = [m["name"] for m in menus]
        entities = extract_multi_order(request.query, menu_names)
        entities = _mix_ordinal_with_named(request.query, entities, menu_names)

        if all(_is_noise_menu(e.get("menu")) for e in entities):
            ordinal_entities = (_resolve_ordinal_orders(request.query)
                                or [e for e in [_resolve_by_recommended(request.query) or _resolve_single_recommended(request.query)
                                              or _resolve_last_asked(request.query)] if e])
            ambiguous = None if ordinal_entities else _ambiguous_menu_question(request.query, menus)
            if ordinal_entities:
                entities = ordinal_entities
            elif ambiguous:
                _pending_temp[:] = [x for x in [_temp_prefix(request.query)] if x]
                _last_recommended_menus[:] = ambiguous[1]
                return {"question": request.query, "intent": "recommend", "answer": ambiguous[0],
                        "recommended_menus": ambiguous[1]}
            elif category := _category_question(request.query, menus):
                answer, shown = category
                _pending_temp[:] = [x for x in [_temp_prefix(request.query)] if x]
                _last_recommended_menus[:] = shown
                return {"question": request.query, "intent": "recommend", "answer": answer,
                        "recommended_menus": shown}
            elif _DISCOUNT_QUESTION_PATTERN.search(request.query):
                return {"question": request.query, "intent": "qa",
                        "answer": _qa_answer(request.query, request.cart_items)}
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

        orders, named, sold_out, stock_notices, notices = _prepare_orders(entities, menus, request.cart_items)
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
        entities = extract_multi_order(request.query, menu_names)
        entities = _mix_ordinal_with_named(request.query, entities, menu_names)
        if all(not e.get("menu") for e in entities):
            entities = (_resolve_ordinal_orders(request.query)
                        or apply_discount_menu_fallback(entities, request.query, menu_names))

        orders, named, sold_out, stock_notices, notices = _prepare_orders(entities, menus, request.cart_items)
        notices = stock_notices + notices
        if not extract_payment_method(request.query) or ((sold_out or stock_notices) and not named):
            return _order_response(request.query, orders, named, sold_out, menus, notices)
        return _order_and_pay_now(request.query, orders, named, sold_out, menus, notices)
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
        return {"question": request.query, "intent": intent, "answer": _qa_answer(request.query, request.cart_items)}
