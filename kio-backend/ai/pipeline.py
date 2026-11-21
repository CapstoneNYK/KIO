# [pipeline.py] 손님 말 한 줄을 처리하는 본체. main.py 의 _handle_ask_inner() 를 단계별 함수로 나눠 옮겼다.
# 처리 순서(우선순위)는 handle_ask() 안의 위→아래 순서와 같다:
#   0) 오타 교정·별칭 풀기·'응/그걸로' 처리
#   1) 열린 되묻기(dialog) 답변  2) 장바구니 명령  3) 요청사항 메모  4) LLM 없이 바로 답하는 안내들
#   5) 의도 분류(규칙 → LLM) 후 order / coupon / recommend / order_and_pay / payment / 그 외(qa)
# 각 단계 함수(_step_*)는 '내가 처리할 말이면 응답 dict, 아니면 None' 을 돌려주고, None 이면 다음 단계로 내려간다.
import re
from dataclasses import dataclass
from functools import partial

from ai import data_source
from ai.cart_command import detect_cart_command, parse_cart
from ai.dialog import answer_slot, current_question, start_dialog
from ai.entity import extract_attributes, extract_menu, extract_multi_order, fix_stt_errors
from ai.fast_intent import fast_classify
from ai.followup import (
    affirm_to_order,
    alternatives_map,
    mix_ordinal_with_named,
    remember_asked,
    remember_pending_temp,
    remember_recommended,
    resolve_by_recommended,
    resolve_last_asked,
    resolve_ordinal_orders,
    resolve_single_recommended,
)
from ai.intent import classify_intent
from ai.korean import normalize_text
from ai.logging_utils import log_intent_query
from ai.memo import memo_menu, memo_request, order_memo, with_memo
from ai.menu_match import alias_answer, ingredient_answer, resolve_owned_aliases
from ai.order import (
    _is_noise_menu,
    apply_discount_menu_fallback,
    cart_answer,
    entities_to_orders,
    limit_by_stock,
    split_sold_out,
    validate_options,
)
from ai.payment import extract_payment_method, get_payment_response, payment_label
from ai.preference import recommend_by_conditions
from ai.quick_answers import (
    CATEGORY_ASK,
    DISCOUNT_QUESTION_PATTERN,
    RE_DISCOUNT_INFO,
    RE_DISCOUNT_SPECIFIC,
    RE_POPULAR,
    ambiguous_menu_question,
    category_question,
    discount_info_answer,
    popular_answer,
    temperature_answer,
)
from ai.recommend import RecommendOutput, qa_chain, recommend_chain
from ai.session import current_state, set_session


# ── 응답을 만드는 보조 함수들 ──
# LLM(Ollama)이 꺼져 있거나 늦을 때 쓰는 대체 답변
_LLM_FAIL_ANSWER = "지금은 답변을 준비하지 못했어요. 다시 한 번 말씀해 주세요."


# 추천: ① 규칙 기반(맛·온도 조건) 먼저 → 없으면 ② LLM 체인. LLM 이 메뉴판에 없는 이름을 지어내면 걸러 낸다
def recommend_menus(query: str):
    menus = data_source.get_menus()
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
        result.answer = recommend_answer(result.menus, menus)
    return result


# LLM 이 고른 메뉴 이름만 받아 번호 목록 문장을 우리가 만든다(맛 태그는 최대 3개)
def recommend_answer(picked: list[str], menus: list[dict]) -> str:
    by_name = {m["name"]: m for m in menus}
    lines = []
    for i, name in enumerate(picked, 1):
        tags = by_name.get(name.removeprefix("핫 ").removeprefix("아이스 "), {}).get("tags") or []
        lines.append(f"{i}번 {name}" + (f" ({', '.join(tags[:3])})" if tags else ""))
    return "이런 메뉴는 어떠세요?\n" + "\n".join(lines) + "\n마음에 드는 걸 번호나 이름으로 말씀해 주세요."


# 메뉴·할인 질문은 LLM(qa_chain)에 맡긴다. 실패하면 대체 문구
def qa_answer(query: str, cart_items: list[str]) -> str:
    try:
        return qa_chain.invoke({"question": query, "cart_items": cart_items})
    except Exception as e:
        print("안내 답변 오류:", e)
        return _LLM_FAIL_ANSWER


# 장바구니 메뉴별 합계 수량(재고 한도 계산용)
def cart_quantities(cart_items: list[str]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for line in parse_cart(cart_items):
        totals[line["menu"]] = totals.get(line["menu"], 0) + line["quantity"]
    return totals


# 추출한 주문을 품절 분리 → 재고 제한 → 옵션 검증 순서로 다듬는다
def prepare_orders(entities: list[dict], menus: list[dict], cart_items: list[str]):
    """말에서 뽑은 주문을 품절·재고·옵션 규칙에 맞춘다. (주문들, 메뉴가 있는 주문들, 품절 메뉴, 재고 안내, 옵션 안내)"""
    sold_out_names = {m["name"] for m in menus if m["sold_out"]}
    orders, sold_out = split_sold_out(entities_to_orders(entities), sold_out_names)
    orders, stock_notices = limit_by_stock(orders, menus, cart_quantities(cart_items))
    orders, notices = validate_options(orders, menus)
    named = [o for o in orders if o["menu"]]
    return orders, named, sold_out, stock_notices, notices


# 일반 주문 응답 JSON(intent=order) 만들기: 장바구니 담김 안내 + 품절 대체 메뉴 + 메모
def order_response(
    question: str,
    orders: list[dict],
    named: list[dict],
    sold_out: list[str],
    menus: list[dict] | None = None,
    notices: list[str] | None = None,
) -> dict:
    alternatives = alternatives_map(sold_out, menus or [])
    return with_memo({
        "question": question,
        "intent": "order",
        "answer": cart_answer(named, sold_out, alternatives=alternatives, notices=notices),
        "orders": orders,
        "sold_out": sold_out,
        "alternatives": alternatives,
    }, question, named)


# 옵션 되묻기(dialog) 응답 JSON. 되묻는 중에 결제수단까지 말했으면 payment_method 도 함께 준다
def dialog_response(question: str, res: dict, **extra) -> dict:
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


# '결제/카드요' 처럼 지금 바로 결제하겠다는 말(NEG: 가격·방법·할인 질문이면 제외)
_RE_PAY_NOW = re.compile(r"결제|계산|카드요|카드로|카드\s*(?:할게|줄게)|페이로|페이\s*(?:할게|요)")


_RE_PAY_NOW_NEG = re.compile(r"얼마|어떻게|되나요|돼요|가능|할인|쿠폰|말고|아니")


# 주문 문장이 '바로 결제' 의도인지
def wants_pay_now(query: str) -> bool:
    return bool(_RE_PAY_NOW.search(query)) and not _RE_PAY_NOW_NEG.search(query)


# 주문+결제를 한 번에 말한 경우: 되묻지 않고 결제 화면으로 이동(intent=order_and_pay)
def order_and_pay_now(question: str, orders: list[dict], named: list[dict], sold_out: list[str],
                       menus: list[dict], notices: list[str]) -> dict:
    method = extract_payment_method(question)
    label = payment_label(method)
    suffix = f" {label}로 결제 화면으로 이동합니다." if label else " 결제 화면으로 이동합니다."
    alternatives = alternatives_map(sold_out, menus)
    return with_memo({
        "question": question,
        "intent": "order_and_pay",
        "answer": cart_answer(named, sold_out, pay_suffix=suffix, alternatives=alternatives, notices=notices),
        "orders": orders,
        "payment_method": method,
        "sold_out": sold_out,
        "alternatives": alternatives,
    }, question, named)

# ── 요청 처리 ──
# 한 요청 동안 단계들이 같이 쓰는 값. query 는 단계 0 에서 교정된 문장이다.
@dataclass
class Ctx:
    query: str
    cart_items: list
    dialog: dict | None
    session_id: str
    menus: list


# 질문·추천 같은 곁가지 답변이 나가도, 열려 있던 되묻기(dialog)는 잃지 않고 하던 질문을 답변 뒤에 이어서 다시 묻는다
def handle_ask(query: str, cart_items: list, dialog: dict | None, session_id: str = "") -> dict:
    result = handle_ask_inner(query, cart_items, dialog, session_id)
    if (dialog and result.get("intent") in ("qa", "recommend") and result.get("dialog") is None):
        again = current_question(dialog)
        if again:
            result["dialog"] = dialog
            result["answer"] = f"{result.get('answer', '')} {again}".strip()
    return result


def handle_ask_inner(query: str, cart_items: list, dialog: dict | None, session_id: str = "") -> dict:
    set_session(session_id)  # 이 요청이 쓸 세션 지정 → 이후 current_state() 가 이 세션의 상태를 돌려준다

    # [0] 준비: 음성인식 오타 교정 → 이미 권한 별칭 풀기('버블티' → '흑당버블티') → '응/그걸로' 단독 긍정이면 그 메뉴 주문으로
    query = fix_stt_errors(query)
    menus = data_source.get_menus()
    query = resolve_owned_aliases(query, menus, current_state().last_recommended)
    affirmed = affirm_to_order(query, bool(dialog))
    if affirmed:
        query = affirmed
    ctx = Ctx(query, cart_items, dialog, session_id, menus)

    for step in (_step_dialog, _step_cart_command, _step_memo, _step_quick_answers):
        resp = step(ctx)
        if resp is not None:
            return resp

    # [5] 의도 분류: 빠른 규칙(fast_classify) → 애매하면 LLM(classify_intent)
    intent = fast_classify(ctx.query, [m["name"] for m in ctx.menus]) or classify_intent(ctx.query)
    log_intent_query(ctx.query, intent)

    if intent == "order":
        return _handle_order(ctx)
    if intent == "coupon":
        return {"question": ctx.query, "intent": "coupon", "answer": "쿠폰 바코드를 카메라로 스캔해볼게요!"}
    if intent == "recommend":
        result = recommend_menus(ctx.query)
        remember_recommended(result.menus)
        return {"question": ctx.query, "intent": intent, "answer": result.answer, "recommended_menus": result.menus}
    if intent == "order_and_pay":
        return _handle_order_and_pay(ctx)
    if intent == "payment":
        answer, payment_method = get_payment_response(ctx.query)
        return {"question": ctx.query, "intent": "payment", "answer": answer, "payment_method": payment_method}
    # 그 외(qa 등): 방금 물어본 메뉴를 기억해 두고(다음 "그걸로 주세요" 용) LLM 안내로 답한다
    remember_asked(extract_menu(ctx.query, [m["name"] for m in ctx.menus]))
    return {"question": ctx.query, "intent": intent, "answer": qa_answer(ctx.query, ctx.cart_items)}


# [1] 열려 있는 옵션 되묻기가 있으면 먼저 그 답으로 해석(온도·샷·연하게 등). 아니면 None 이 돌아와 아래로 내려간다
def _step_dialog(ctx: Ctx) -> dict | None:
    if not ctx.dialog:
        return None
    slot_res = answer_slot(ctx.dialog, ctx.query, ctx.menus, ctx.cart_items,
                           partial(detect_cart_command, session_id=ctx.session_id))
    if slot_res is None:
        return None
    resp = dialog_response(ctx.query, slot_res)
    if resp.get("memo"):
        resp["memo_menu"] = memo_menu(ctx.query, ctx.cart_items, ctx.dialog)
    return resp


# [2] 장바구니 명령('아메리카노 빼줘', '다 아이스로') — 명령이 아니면 None
def _step_cart_command(ctx: Ctx) -> dict | None:
    command = detect_cart_command(ctx.query, ctx.cart_items, ctx.menus, session_id=ctx.session_id)
    return {"question": ctx.query, **command} if command else None


# [3] 담아 둔 메뉴에 대한 요청사항 메모
def _step_memo(ctx: Ctx) -> dict | None:
    return memo_request(ctx.query, ctx.menus, ctx.cart_items, ctx.dialog)


# [4] LLM 없이 규칙으로 바로 답하는 질문들(인기 메뉴 → 할인 목록 → 종류 목록 → 별칭/재료 → 온도 가능 여부)
def _step_quick_answers(ctx: Ctx) -> dict | None:
    query, menus = ctx.query, ctx.menus
    menu_names = [m["name"] for m in menus]
    qn = normalize_text(query)
    if RE_POPULAR.search(qn):
        answer, popular = popular_answer(menus)
        remember_recommended(popular)
        return {"question": query, "intent": "recommend", "answer": answer, "recommended_menus": popular}
    if RE_DISCOUNT_INFO.search(qn) and not RE_DISCOUNT_SPECIFIC.search(qn) and not extract_menu(query, menu_names):
        return {"question": query, "intent": "qa", "answer": discount_info_answer()}

    if CATEGORY_ASK.search(qn) and not extract_menu(query, menu_names):
        category = category_question(query, menus)  # "스무디 종류 뭐 있어?" — LLM 없이 목록으로 답한다
        if category:
            answer, shown = category
            remember_pending_temp(query)
            remember_recommended(shown)
            return {"question": query, "intent": "recommend", "answer": answer, "recommended_menus": shown}

    for matched in (alias_answer(query, menus), ingredient_answer(query, menus)):
        if matched:  # 메뉴판에 없는 이름 -> 비슷한 메뉴 / 재료·과일이 들어간 메뉴 목록
            remember_recommended(matched[1])
            return {"question": query, "intent": "recommend", "answer": matched[0], "recommended_menus": matched[1]}

    temp_answer = temperature_answer(query, menus)
    if temp_answer:
        return {"question": query, "intent": "qa", "answer": temp_answer}
    return None


# 주문: 메뉴 추출 → (메뉴가 없으면 번호/추천/종류/질문/취향 추천 중 하나로 해석) → 품절·재고·옵션 정리 → 되묻기 시작 또는 바로 담기
def _handle_order(ctx: Ctx) -> dict:
    menus = ctx.menus
    menu_names = [m["name"] for m in menus]
    entities = extract_multi_order(ctx.query, menu_names)
    entities = mix_ordinal_with_named(ctx.query, entities, menu_names)

    if all(_is_noise_menu(e.get("menu")) for e in entities):
        entities, early = _resolve_nameless_order(ctx, entities, menu_names)
        if early is not None:
            return early

    orders, named, sold_out, stock_notices, notices = prepare_orders(entities, menus, ctx.cart_items)
    if named and wants_pay_now(ctx.query):
        # "아아 두 잔 결제", "라떼 하나 카드요"처럼 주문과 결제를 한 번에 말하면 되묻지 않고 바로 결제로 간다
        return order_and_pay_now(ctx.query, orders, named, sold_out, menus, stock_notices + notices)
    started = start_dialog(named, menus) if named else None
    if started is not None:
        # 온도를 되물을 거라 '아이스로 담았어요' 안내는 뺀다
        keep = [n for n in stock_notices + notices if not n.startswith("온도를 말씀하지 않으셔서")]
        if sold_out or keep:
            started["answer"] = cart_answer(
                [], sold_out, alternatives=alternatives_map(sold_out, menus), notices=keep
            ) + " " + started["answer"]
        return dialog_response(ctx.query, started, sold_out=sold_out, **order_memo(ctx.query, named))
    notices = stock_notices + notices
    return order_response(ctx.query, orders, named, sold_out, menus, notices)


# 주문인데 메뉴 이름을 하나도 못 찾았을 때의 보조 해석(위에서 아래로 첫 성공):
#   번호 선택 → 추천 대상 → 이름 겹침 되묻기 → 종류 목록 → 할인 질문 → 취향 추천 → 할인 메뉴 대체
# (바뀐 주문 목록, 바로 돌려줄 응답) 을 반환. 응답이 None 이면 주문 목록으로 계속 진행한다.
def _resolve_nameless_order(ctx: Ctx, entities: list, menu_names: list):
    query, menus = ctx.query, ctx.menus
    ordinal_entities = (resolve_ordinal_orders(query)
                        or [e for e in [resolve_by_recommended(query) or resolve_single_recommended(query)
                                        or resolve_last_asked(query)] if e])
    if ordinal_entities:
        return ordinal_entities, None
    ambiguous = ambiguous_menu_question(query, menus)
    if ambiguous:
        remember_pending_temp(query)
        remember_recommended(ambiguous[1])
        return entities, {"question": query, "intent": "recommend", "answer": ambiguous[0],
                          "recommended_menus": ambiguous[1]}
    category = category_question(query, menus)
    if category:
        answer, shown = category
        remember_pending_temp(query)
        remember_recommended(shown)
        return entities, {"question": query, "intent": "recommend", "answer": answer, "recommended_menus": shown}
    if DISCOUNT_QUESTION_PATTERN.search(query):
        return entities, {"question": query, "intent": "qa", "answer": qa_answer(query, ctx.cart_items)}
    if extract_attributes(query) and all(
            _is_noise_menu(e.get("menu"))
            for e in apply_discount_menu_fallback(entities, query, menu_names)):
        # "시원한 거 하나 주세요", "달달한 걸로"처럼 메뉴 없이 취향만 말하면 추천으로 이어 간다
        result = recommend_menus(query)
        remember_recommended(result.menus)
        return entities, {"question": query, "intent": "recommend", "answer": result.answer,
                          "recommended_menus": result.menus}
    return apply_discount_menu_fallback(entities, query, menu_names), None


# 주문+결제를 한 번에 말한 경우(intent=order_and_pay): 결제수단이 없거나 품절·재고 문제로 담을 게 없으면 일반 주문 응답, 아니면 바로 결제 화면
def _handle_order_and_pay(ctx: Ctx) -> dict:
    menus = ctx.menus
    menu_names = [m["name"] for m in menus]
    entities = extract_multi_order(ctx.query, menu_names)
    entities = mix_ordinal_with_named(ctx.query, entities, menu_names)
    if all(not e.get("menu") for e in entities):
        entities = (resolve_ordinal_orders(ctx.query)
                    or apply_discount_menu_fallback(entities, ctx.query, menu_names))

    orders, named, sold_out, stock_notices, notices = prepare_orders(entities, menus, ctx.cart_items)
    notices = stock_notices + notices
    if not extract_payment_method(ctx.query) or ((sold_out or stock_notices) and not named):
        return order_response(ctx.query, orders, named, sold_out, menus, notices)
    return order_and_pay_now(ctx.query, orders, named, sold_out, menus, notices)
