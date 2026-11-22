# [memo.py] 요청사항 메모: "딸기라떼 우유는 저지방으로", "녹차라떼 덜 달게 줘"처럼 옵션으로 못 담는 요청을
# 새 주문이 아니라 '메모(memo, memo_menu)'로 적는 규칙들. main.py 에서 분리했다.
import re

from ai.dialog import _refers_to
from ai.entity import extract_option_details
from ai.korean import normalize_text


# '요청사항 메모' 판정용 패턴: CUE=메모로 적을 만한 말(저지방/덜 달게/펄…), NOT=그래도 메모가 아닌 말(결제/취소/가격 질문…)
_RE_REQUEST_CUE = re.compile(
    r"저지방|무지방|두유|오트|귀리|아몬드|우유|덜\s*달|달게|달지|시럽|설탕|얼음|휘핑|크림|미지근|싱겁|넣지|"
    r"빼\s*(?:줘|주세요|달라|고)|많이|적게|조금만|따로|디카페인|빨대|리필|알레르기|펌프|펄|타피오카|젤리")


_RE_REQUEST_NOT = re.compile(r"더\s*(?:주세요|줘|추가)|하나\s*더|한\s*잔\s*더|결제|계산|취소|삭제|지워|얼마|가격|뭐|"
                             r"있나요|있어요|있어\?|되나요|돼요|가능|알려")


# 장바구니 한 줄에서 수량·옵션을 뗀 음료 이름만 뽑는다
def _cart_label(line: str) -> str:
    """장바구니 줄("아이스 딸기 라떼 ×2 (시럽 적게)")에서 음료 이름만: "아이스 딸기 라떼"."""
    return re.split(r"\s+×\d+|\s+\(", line, maxsplit=1)[0].strip()


# '여기/이거/방금' 같이 바로 앞 음료를 가리키는 말
_RE_DEICTIC = re.compile(r"여기|거기|이거|그거|이것|그것|방금|이\s*음료|이\s*메뉴")


# 요청사항이 어느 음료에 대한 것인지 정한다: 말한 음료 → 장바구니에 한 종류뿐이면 그것 → '여기에' 면 방금 담은 음료 → 아니면 None(주문 전체)
def memo_menu(query: str, cart_items: list[str], dialog: dict | None = None) -> str | None:
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


# 이미 담은 메뉴에 대한 추가 요청('우유는 저지방으로')은 새 주문이 아니라 요청사항 메모로 돌려준다. 새 메뉴를 말했거나 정식 옵션(샷 등)이면 None
def memo_request(query: str, menus: list[dict], cart_items: list[str], dialog: dict | None = None) -> dict | None:
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
            "memo_menu": memo_menu(query, cart_items, dialog)}


# 주문 문장에 섞인 '덜 달게/저지방 우유/펄 많이' 등 옵션으로 못 담는 요청 표현
_RE_ORDER_MEMO = re.compile(
    r"(?:(?:조금|살짝|아주|너무)\s*)?(?:덜|안)\s*달게|달지\s*않게|달지\s*않은\s*걸?로?|덜\s*단\s*걸?로?|(?:조금|많이)\s*달게|싱겁게|"
    r"(?:저지방|무지방|두유|오트(?:밀)?|귀리|아몬드)\s*우유(?:로)?|우유[는를]?\s*(?:저지방|무지방|두유|오트|귀리|아몬드)\S*|"
    r"펄\s*(?:많이|적게|빼고|조금)|젤리\s*(?:많이|적게|빼고)|빨대\s*(?:빼|없이)|얼음\s*(?:많이|적게|조금만?|빼고)")


# 주문에 옵션으로 못 담는 요청이 섞여 있으면 요청사항 메모(memo, memo_menu)로 따로 뽑는다
def order_memo(query: str, named: list[dict]) -> dict:
    """"녹차라떼 덜 달게 따뜻하게 줘"처럼 옵션으로 담을 수 없는 요청이 주문에 섞여 있으면 요청사항 메모로도 남긴다."""
    if not named or extract_option_details(query):
        return {}
    hits = [m.group(0).strip() for m in _RE_ORDER_MEMO.finditer(query)]
    if not hits:
        return {}
    labels = [f"{'아이스' if o.get('temperature') == 'ICE' else '따뜻한'} {o['menu']}" for o in named]
    return {"memo": " ".join(dict.fromkeys(hits)), "memo_menu": ", ".join(dict.fromkeys(labels))}


# 응답 dict 에 메모가 있으면 합치고 답변 끝에 '요청사항도 적어 둘게요'를 붙인다
def with_memo(resp: dict, query: str, named: list[dict]) -> dict:
    extra = order_memo(query, named)
    if extra:
        resp.update(extra)
        resp["answer"] = f"{resp['answer']} '{extra['memo']}' 요청사항도 적어 둘게요."
    return resp
