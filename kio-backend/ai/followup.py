# [followup.py] '앞 말을 이어받는' 해석들. main.py 에서 분리했다.
#  - "1번 주세요", "그걸로 두 잔", "그럼 아이스로 하나 줘"처럼 메뉴 이름 없이 앞에 보여 준 목록/물어본 메뉴를 가리키는 말
#  - 번호와 메뉴 이름이 섞인 주문, 품절 대체 메뉴 기억, 종류 고르기 전에 말한 온도 이어 붙이기
# 상태(방금 추천한 메뉴·방금 물어본 메뉴·먼저 말한 온도)는 ai.session 의 세션별 상태(current_state())에 둔다.
import re

from ai.entity import (
    MULTI_SPLIT_PATTERN,
    extract_attributes,
    extract_menu,
    extract_multi_order,
    extract_option_details,
    extract_options_from_text,
    extract_ordinal_segments,
    extract_packaging,
    extract_quantity,
    fix_stt_errors,
)
from ai.dialog import _HOT as _HOT_W, _ICE as _ICE_W
from ai.korean import normalize_text
from ai.order import _is_noise_menu
from ai.preference import find_alternatives
from ai.session import current_state


# 메뉴 이름 + 말에서 뽑은 수량·온도·옵션·포장으로 '주문 한 건'(엔티티 dict)을 만든다.
# 예전에는 같은 dict 를 네 곳에서 따로 만들었다. quantity 를 직접 주면 그 값을 쓴다.
def entity_for(menu: str, query: str, quantity: int | None = None) -> dict:
    return {
        "menu": menu,
        "quantity": extract_quantity(query) if quantity is None else quantity,
        "attributes": extract_attributes(query),
        "options": extract_options_from_text(query),
        "option_details": extract_option_details(query),
        "packaging": extract_packaging(query),
        "needs_recommendation": False,
    }


# '방금 추천한 메뉴'를 기억한다(다음 "1번 주세요"의 대상). 예전의 _last_recommended_menus[:] = ...
def remember_recommended(menus: list[str]) -> None:
    current_state().last_recommended[:] = menus


# '방금 물어본 메뉴'를 기억한다(가격·재료 질문 뒤 "그걸로 주세요"의 대상). 예전의 _last_asked[:] = ...
def remember_asked(menu: str | None) -> None:
    current_state().last_asked[:] = [menu] if menu else []


# 종류를 고르기 전에 말한 온도('핫'/'아이스')를 기억한다. 온도가 없거나 둘 다 있으면 비운다
def remember_pending_temp(query: str) -> None:
    current_state().pending_temp[:] = [x for x in [temp_prefix(query)] if x]


# 추천 메뉴가 하나뿐일 때 '응/그걸로' 만 말하면 그 메뉴를 한 잔 주문하는 문장으로 바꿔 준다(아니면 None).
# 한 번 쓰면 기억을 비운다. 열린 되묻기(dialog)가 있으면 그 답일 수 있으니 건드리지 않는다.
def affirm_to_order(query: str, has_dialog: bool) -> str | None:
    st = current_state()
    if len(st.last_recommended) == 1 and not has_dialog and _RE_AFFIRM.match(normalize_text(query)):
        menu = st.last_recommended[0]
        st.last_recommended.clear()
        return f"{menu} 하나 주세요"
    return None


# '네/응/그걸로' 같은 짧은 긍정. 추천 메뉴가 하나뿐일 때 이 말이면 그 메뉴를 주문으로 본다
_RE_AFFIRM = re.compile(r"^(?:네|넵|예|응|어|음|그래|그래요|좋아|좋아요|그럼|맞아|맞아요|그걸로|그거|그걸로요|그걸로할게|그걸로주세요|그걸로줘)[.!~요]*$")


# '그걸/그거/이거' 처럼 앞의 메뉴를 가리키는 말
_RE_THAT_ONE = re.compile(r"그럼|그걸|그거|그것|거기|이걸|이거|저걸|저거|그걸루")


# 메뉴 이름을 공백으로 나눈 2글자 이상 단어들('딸기 라떼' → ['딸기','라떼'])
def menu_words(name: str) -> list[str]:
    return [w for w in name.split() if len(w) >= 2]


# 말 속 단어가 방금 추천한 메뉴 중 정확히 하나와 겹치면 그 메뉴로 주문 한 건을 만든다('딸기 하나 줘' → 추천 목록의 딸기라떼)
def resolve_by_recommended(query: str) -> dict | None:
    qn = normalize_text(query)
    cands = []
    for rec in current_state().last_recommended:
        base = rec.removeprefix("핫 ").removeprefix("아이스 ")
        if any(normalize_text(w) in qn for w in menu_words(base)):
            cands.append(rec)
    if len(cands) != 1:
        return None
    return entity_for(cands[0], query)


# 추천이 딱 하나였을 때 '그걸로 두 잔'을 그 메뉴 주문으로 만든다(한 번 쓰면 비워서 나중의 '그거'가 옛 추천을 또 주문하지 않게 함)
def resolve_single_recommended(query: str) -> dict | None:
    """방금 메뉴를 하나만 권했다면 "그걸로 두 잔 줘", "어 그거 하나"는 그 메뉴를 가리킨다."""
    if len(current_state().last_recommended) != 1 or not _RE_THAT_ONE.search(query):
        return None
    menu = current_state().last_recommended[0]
    current_state().last_recommended.clear()  # 한 번 주문에 쓰면 비워서, 나중의 "그거"가 옛 추천을 다시 주문하지 않게 한다
    return entity_for(menu, query)


# 방금 물어본 메뉴(가격 등)를 '그럼 그걸로 주세요'로 받아 주문으로 만든다. [겹침] 위 resolve_single_recommended 와 거의 같은 구조
def resolve_last_asked(query: str) -> dict | None:
    """"카페라떼 얼마예요?" → "그럼 아이스로 하나 주세요": 방금 물어본 메뉴를 가리키는 말이면 그 메뉴로 받는다."""
    if len(current_state().last_asked) != 1 or not _RE_THAT_ONE.search(query):
        return None
    menu = current_state().last_asked[0]
    current_state().last_asked.clear()
    return entity_for(menu, query)


# '둘 다/전부/모두' — 방금 보여 준 목록을 전부 고른다는 말
_RE_ALL_SHOWN = re.compile(r"[둘셋넷]\s*(?:다|모두|전부)|전부|모두|각각|다\s*(?:주세요|줘|주라|할게|먹)")


# 수량을 명시했는지('두 잔') / 여러 메뉴에 같은 수량을 나눠 적용하는 말('씩', '각각', '둘 다')
_RE_EXPLICIT_QTY = re.compile(r"\d+\s*[잔개컵]|(?:한|두|세|네|다섯|여섯)\s*[잔개컵]|하나|둘(?!\s*(?:다|모두|전부))|셋|넷")


_RE_SHARED_QTY = re.compile(r"씩|각각|[둘셋넷]\s*(?:다|모두|전부)|모두|전부")


# 수량이 명시돼 있으면 그 수량, 아니면 None
def _explicit_qty(seg: str) -> int | None:
    return extract_quantity(seg) if _RE_EXPLICIT_QTY.search(seg) else None


# 말 속 온도가 한쪽뿐이면 '핫'/'아이스', 둘 다 있거나 없으면 None (ai.dialog 의 _HOT/_ICE 사용)
def temp_prefix(query: str) -> str | None:
    t = normalize_text(query)
    hot, ice = bool(_HOT_W.search(t)), bool(_ICE_W.search(t))
    return "핫" if hot and not ice else "아이스" if ice and not hot else None


# 추천 목록에서 '2번 하나랑 3번 두 개'처럼 번호로 고른 주문을 만든다. '둘 다/전부'면 목록 전체. 목록 보여 주기 전에 말한 온도(pending_temp)를 이어 붙인다
def resolve_ordinal_orders(query: str) -> list[dict]:
    """추천 목록에서 번호로 고른 주문. "2번 하나랑 3번 두 개"처럼 여러 번호는 번호마다 수량을 따로 읽는다."""
    picks = [(n, seg) for n, seg in extract_ordinal_segments(query) if 1 <= n <= len(current_state().last_recommended)]
    if not picks and len(current_state().last_recommended) >= 2 and _RE_ALL_SHOWN.search(query):
        # "둘 다 한 잔씩", "전부 주세요": 방금 보여 준 목록을 모두 고른 것이다
        picks = [(n, query) for n in range(1, len(current_state().last_recommended) + 1)]
    if not picks:
        return []
    multi = len(picks) > 1 and picks[0][1] != query
    # "1번 2번 둘 다 두 잔씩"처럼 수량을 한 번만 말했으면 고른 메뉴 모두에 같은 수량을 준다
    shared = _explicit_qty(picks[-1][1]) if multi and _RE_SHARED_QTY.search(query) else None
    temp = current_state().pending_temp[0] if current_state().pending_temp and not temp_prefix(query) else None
    current_state().pending_temp.clear()
    entities = []
    for n, seg in picks:
        menu = current_state().last_recommended[n - 1]
        if temp and not menu.startswith(("핫 ", "아이스 ")):
            menu = f"{temp} {menu}"  # 목록을 보여 주기 전에 말한 온도를 이어 간다
        entities.append(entity_for(
            menu, query, quantity=((_explicit_qty(seg) or shared or 1) if multi else extract_quantity(query))))
    return entities


# '1번으로 따뜻하게 두 잔이랑 레몬에이드 한 잔'처럼 번호와 메뉴 이름이 섞인 주문을 말 조각별로 나눠 따로 읽어 합친다
def mix_ordinal_with_named(query: str, entities: list[dict], menu_names: list[str]) -> list[dict]:
    """"1번으로 따뜻하게 두 잔이랑 레몬에이드 한 잔"처럼 추천 목록의 번호와 메뉴 이름을 함께 말한 주문.
    번호 부분은 추천 목록에서, 이름 부분은 메뉴 이름으로 따로 읽어 합친다(이름만 읽으면 번호 부분이 빠진다)."""
    if not current_state().last_recommended or all(_is_noise_menu(e.get("menu")) for e in entities):
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
        picked = resolve_ordinal_orders(part)
        if picked:
            ordinal_parts += 1
            merged += picked
    return merged if ordinal_parts and merged else entities


# 품절 메뉴마다 대체 메뉴를 찾아 {품절: [대체...]} 로 만들고, 첫 대체 목록을 '방금 추천'으로 기억한다(다음 '1번 주세요' 용)
def alternatives_map(sold_out: list[str], menus: list[dict]) -> dict[str, list[str]]:
    alternatives = {}
    for name in sold_out:
        alts = find_alternatives(name, menus)
        if alts:
            alternatives[name] = alts
    if alternatives:
        current_state().last_recommended[:] = next(iter(alternatives.values()))
    return alternatives
