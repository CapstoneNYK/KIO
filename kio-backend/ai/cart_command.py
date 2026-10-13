"""장바구니 취소·변경 명령 감지 (규칙 기반).

왜 LLM이 아니라 규칙인가
- 장바구니를 직접 바꾸는 동작이라 오분류의 비용이 크다("아메리카노 시럽 빼고 주세요"가 취소로 분류되면 안 됨).
- 로컬 7B 모델의 의도 분류보다 규칙이 결정적이고 빠르다.
- 모호하면 실행하지 않고 되묻는다(어떤 메뉴를 취소할지 등).

반환 형식 (명령이 아니면 None)
{
  "intent": "cancel" | "modify",
  "answer": "사용자에게 보여줄 안내",
  "cart_actions": [  # 프론트가 장바구니에 그대로 적용
      {"type": "remove_all"},
      {"type": "remove_last"},
      {"type": "remove_item", "menu": "아메리카노", "temperature": "ICE"|"HOT"|None},
      {"type": "set_quantity", "menu": "...", "quantity": 3, "temperature": None},
      {"type": "set_temperature", "menu": "...", "temperature": "HOT"},
      {"type": "replace_item", "menu": "아메리카노", "to_menu": "카페라떼"},
  ]
}
"""

import re
from typing import Optional

from ai.entity import extract_menu, normalize_text


def _rx(pattern: str) -> "re.Pattern":
    return re.compile(normalize_text(pattern))


# 과거형(결제했/결제한/계산된...)일 때만 "이미 끝난 주문"으로 본다. "결제 취소할게"는 결제 진행 중 취소일 수 있어 제외.
_RE_POST_PAY = _rx(r"(결제|계산|주문)(?:을|를)?(?:한|했|된|완료|끝).{0,8}(취소|환불)|환불")
_RE_ALL = _rx(
    r"(?:다|전부|전체|모두|싹|주문|장바구니)(?:를|을|은|는|다)?(?:다)?"
    r"(?:취소|삭제|지워|지우|비워|비우|초기화|리셋)|처음부터|다시시작|전부빼|다빼|모두빼"
)
_RE_LAST = _rx(r"(방금|마지막|아까|조금전|금방)(?:것|거|껀|걸|담은|넣은)?")
_RE_THAT = _rx(r"(?:그거|그건|이거|이건|그걸|이걸)(?:는|은)?(?:좀)?(?:취소|빼|삭제|지워)")

_RE_CANCEL_STRONG = _rx(r"취소|삭제|지워|지우|제거|필요없|안마실|안할래|안먹")
_RE_CANCEL_WEAK = _rx(r"빼줘|빼주|빼요|빼고싶|빼버려|빼자|빼라|빼")
# "시럽 빼고 주세요"처럼 옵션을 빼는 말은 취소가 아니다
_OPTION_WORDS = tuple(normalize_text(w) for w in ("시럽", "크림", "샷", "얼음", "휘핑", "우유", "설탕", "토핑", "연하게"))

_RE_CHANGE = _rx(r"바꿔|바꾸|바꿀|바꿔줘|변경|수정|고쳐|줄여|늘려")
_RE_REPLACE_SPLIT = _rx(r"말고|대신")

_NUM = r"(\d+|한|하나|두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)"
_NUM_WORDS = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4,
              "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
_RE_QTY = _rx(_NUM + r"(?:(?:개|잔|병)(?:만|으로|로)?|(?:으로|로|만))(?:바꿔|변경|수정|해줘|해주세요|줄여|늘려|할게|만)?")
_RE_MORE = _rx(r"(?:\d+|한|하나|두|둘|세|셋|네|넷)(?:개|잔|병)?더")
_RE_HOT = _rx(r"핫|따뜻|뜨거|뜨겁|hot")
_RE_ICE = _rx(r"아이스|차가|차갑|시원|ice")

_RE_NON_CART = _rx(r"결제|카드|쿠폰|계산|카카오|네이버|할인|상품권|멤버십")

MAX_QTY = 20


def _has_final(word: str) -> bool:
    ch = word[-1]
    code = ord(ch)
    return 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 != 0


def _eul(word: str) -> str:
    return f"{word}{'을' if _has_final(word) else '를'}"


def _eun(word: str) -> str:
    return f"{word}{'은' if _has_final(word) else '는'}"


def _parse_cart(cart_items: list) -> list:
    """프론트가 보내는 장바구니 문자열("아이스 아메리카노", "따뜻한 카페라떼")을 분해한다."""
    parsed = []
    for raw in cart_items or []:
        raw = raw.strip()
        if raw.startswith("아이스 "):
            parsed.append({"menu": raw[len("아이스 "):], "temperature": "ICE"})
        elif raw.startswith("따뜻한 "):
            parsed.append({"menu": raw[len("따뜻한 "):], "temperature": "HOT"})
        else:
            parsed.append({"menu": raw, "temperature": None})
    return parsed


def _cart_text(cart: list) -> str:
    if not cart:
        return "장바구니가 비어 있어요."
    names = ", ".join(
        f"{'아이스' if c['temperature'] == 'ICE' else '따뜻한' if c['temperature'] == 'HOT' else ''} {c['menu']}".strip()
        for c in cart
    )
    return f"현재 장바구니: {names}"


def _weak_cancel_applies(t: str) -> bool:
    """'빼' 계열은 바로 앞이 옵션 단어이면 취소가 아니다."""
    for m in _RE_CANCEL_WEAK.finditer(t):
        before = t[max(0, m.start() - 6):m.start()]
        if not any(w in before for w in _OPTION_WORDS):
            return True
    return False


def _temp_in(text_norm: str) -> Optional[str]:
    hot, ice = bool(_RE_HOT.search(text_norm)), bool(_RE_ICE.search(text_norm))
    if hot and not ice:
        return "HOT"
    if ice and not hot:
        return "ICE"
    return None


def _result(intent: str, answer: str, actions: Optional[list] = None) -> dict:
    return {"intent": intent, "answer": answer, "cart_actions": actions or []}


def detect_cart_command(text: str, cart_items: list, menus: list) -> Optional[dict]:
    t = normalize_text(text)
    menu_names = [m["name"] for m in menus]
    by_name = {m["name"]: m for m in menus}
    cart = _parse_cart(cart_items)
    cart_menus = [c["menu"] for c in cart]

    # 0) 결제가 끝난 주문의 취소/환불: 키오스크에서 처리하지 않고 안내만 한다 (정책은 문서 참조)
    if _RE_POST_PAY.search(t):
        return _result(
            "cancel",
            "결제 직후 화면의 '주문 취소' 버튼으로 결제 후 3분 안에 취소할 수 있어요. 시간이 지났다면 카운터 직원에게 말씀해 주세요.",
        )

    has_all = bool(_RE_ALL.search(t))
    has_cancel = bool(_RE_CANCEL_STRONG.search(t)) or _weak_cancel_applies(t) or bool(_RE_THAT.search(t))
    has_change = bool(_RE_CHANGE.search(t))
    has_replace = bool(_RE_REPLACE_SPLIT.search(t))

    if not (has_all or has_cancel or has_change or has_replace):
        return None

    # 1) "A 말고 B로 바꿔줘" — 메뉴 교체 (장바구니에 A가 있을 때만 명령으로 본다)
    if has_replace:
        m = _RE_REPLACE_SPLIT.search(t)
        left, right = t[:m.start()], t[m.end():]
        from_menu = extract_menu(left, menu_names)
        to_menu = extract_menu(right, menu_names)
        if from_menu and to_menu and from_menu != to_menu and from_menu in cart_menus:
            if by_name.get(to_menu, {}).get("sold_out"):
                return _result("modify", f"{_eun(to_menu)} 현재 품절이에요. 다른 메뉴로 바꿔드릴까요?")
            return _result(
                "modify",
                f"{_eun(from_menu)} 빼고 {_eul(to_menu)} 담았어요.",
                [{"type": "replace_item", "menu": from_menu, "to_menu": to_menu}],
            )
        if from_menu and from_menu not in cart_menus and to_menu and not has_cancel and not has_change:
            return None  # 장바구니와 무관한 일반 주문 발화일 수 있어 기존 흐름에 맡긴다

    # 2) 전체 취소
    if has_all:
        if not cart:
            return _result("cancel", "장바구니가 이미 비어 있어요.")
        return _result("cancel", "장바구니를 모두 비웠어요. 처음부터 다시 주문해 주세요.", [{"type": "remove_all"}])

    target = extract_menu(text, menu_names)
    target_temp = _temp_in(t)

    # 3) 메뉴 취소
    if has_cancel:
        if _RE_LAST.search(t) or (not target and _RE_THAT.search(t)):
            if not cart:
                return _result("cancel", "장바구니가 비어 있어요.")
            last = cart[-1]
            return _result("cancel", f"방금 담은 {_eul(last['menu'])} 뺐어요.", [{"type": "remove_last"}])
        if target:
            if target not in cart_menus:
                return _result("cancel", f"장바구니에 {_eun(target)} 없어요. {_cart_text(cart)}")
            temp = target_temp if sum(1 for c in cart if c["menu"] == target) > 1 else None
            return _result(
                "cancel",
                f"{_eul(target)} 장바구니에서 뺐어요.",
                [{"type": "remove_item", "menu": target, "temperature": temp}],
            )
        if _RE_NON_CART.search(t):
            return None  # 결제/쿠폰 관련 취소 발화는 기존 흐름에 맡긴다
        if not cart:
            return _result("cancel", "장바구니가 비어 있어요.")
        return _result(
            "cancel",
            f"어떤 메뉴를 취소할까요? 전부 지우려면 '전부 취소'라고 말씀해 주세요. {_cart_text(cart)}",
        )

    # 4) 수량/온도 변경
    if has_change:
        if _RE_MORE.search(t):
            return None  # "한 잔 더"는 수량 지정이 아니라 추가 주문 → 기존 주문 흐름에 맡긴다
        qty_match = _RE_QTY.search(t)
        temp_req = target_temp
        if not (qty_match or temp_req):
            return None

        menu = target
        if not menu:
            if len(cart) == 1:
                menu = cart[0]["menu"]
            elif not cart:
                return _result("modify", "장바구니가 비어 있어요. 먼저 메뉴를 담아주세요.")
            else:
                return _result("modify", f"어떤 메뉴를 바꿀까요? 메뉴 이름과 함께 말씀해 주세요. {_cart_text(cart)}")
        if menu not in cart_menus:
            return _result("modify", f"장바구니에 {_eun(menu)} 없어요. {_cart_text(cart)}")

        if qty_match:
            g = qty_match.group(1)
            qty = int(g) if g.isdigit() else _NUM_WORDS.get(g, 1)
            if qty < 1 or qty > MAX_QTY:
                return _result("modify", f"수량은 1~{MAX_QTY}개 사이로 말씀해 주세요.")
            return _result(
                "modify",
                f"{_eul(menu)} {qty}개로 바꿨어요.",
                [{"type": "set_quantity", "menu": menu, "quantity": qty, "temperature": None}],
            )

        info = by_name.get(menu, {})
        if temp_req and info.get("temps") and temp_req not in info["temps"]:
            only = "아이스" if "ICE" in info["temps"] else "따뜻한"
            return _result("modify", f"{_eun(menu)} {only} 음료로만 주문할 수 있어요.")
        label = "아이스" if temp_req == "ICE" else "따뜻한"
        return _result(
            "modify",
            f"{_eul(menu)} {label} 음료로 바꿨어요.",
            [{"type": "set_temperature", "menu": menu, "temperature": temp_req}],
        )

    return None
