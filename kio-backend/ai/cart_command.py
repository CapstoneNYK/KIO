import re
import time
from typing import Optional

from ai.entity import extract_menu, extract_option_details, normalize_text
from ai.order import validate_options


def _rx(pattern: str) -> "re.Pattern":
    return re.compile(normalize_text(pattern))

_RE_POST_PAY = _rx(r"(결제|계산|주문)(?:을|를)?(?:한|했|된|완료|끝).{0,8}(취소|환불)|환불")
_RE_ALL = _rx(
    r"(?:다|전부|전체|모두|싹|주문|장바구니)(?:를|을|은|는|다)?(?:다)?"
    r"(?:취소|삭제|지워|지우|비워|비우|초기화|리셋)|처음부터|다시시작|전부빼|다빼|모두빼"
)
_RE_LAST = _rx(r"(방금|마지막|아까|조금전|금방)(?:것|거|껀|걸|담은|넣은)?")
_RE_FIRST = _rx(r"처음|먼저|첫|맨처음|제일처음")
_RE_EVERY = _rx(r"전부|모두|전체|싹|다(?=취소|빼|삭제|지워|지우|없애)")
_RE_CART_WIDE = _rx(r"주문|장바구니|처음부터|다시시작")
_RE_EXISTING = _rx(r"담은|담아둔|시킨|넣은|주문한|담긴|장바구니|있는|방금|아까|처음에")
_RE_PART = _rx(r"(\d+|한|하나|두|둘|세|셋|네|넷)(?:개|잔)?(?:는|만|은)")
_RE_THAT = _rx(r"(?:그거|그건|이거|이건|그걸|이걸)(?:는|은)?(?:좀)?(?:취소|빼|삭제|지워)")

_RE_CANCEL_STRONG = _rx(r"취소|삭제|지워|지우|제거|필요없|안마실|안할래|안먹")
_RE_CANCEL_WEAK = _rx(r"빼줘|빼주|빼요|빼고싶|빼버려|빼자|빼라|빼")
_OPTION_WORDS = tuple(normalize_text(w) for w in ("시럽", "크림", "샷", "얼음", "휘핑", "우유", "설탕", "토핑", "연하게"))

_RE_CHANGE = _rx(r"바꿔|바꾸|바꿀|바꿔줘|변경|수정|고쳐|줄여|늘려")
_RE_REPLACE_SPLIT = _rx(r"말고|대신")

_NUM = r"(\d+|한|하나|두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)"
_NUM_WORDS = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4,
              "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
_RE_QTY = _rx(_NUM + r"(?:(?:개|잔|병)(?:만|으로|로)?|(?:으로|로|만))(?:바꿔|변경|수정|해줘|해주세요|줄여|늘려|할게|만)?")
_RE_MORE = _rx(r"(?:\d+|한|하나|두|둘|세|셋|네|넷)(?:개|잔|병)?더")
_RE_HOT = _rx(r"핫|따뜻|따듯|따스|따숩|따땃|따끈|뜨끈|뜨거|뜨겁|뜨듯|뜨신|hot")
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

_CART_LINE = re.compile(r"^(?:(아이스|따뜻한) )?(.+?)(?: ×(\d+))?(?: \((.*)\))?$")
_OPT_COUNT = re.compile(r"^(.*?)(?: ×(\d+))?$")


def parse_cart(cart_items: list) -> list:
    parsed = []
    for i, raw in enumerate(cart_items or []):
        m = _CART_LINE.match((raw or "").strip())
        if not m:
            parsed.append({"menu": (raw or "").strip(), "temperature": None, "quantity": 1,
                           "options": [], "packaging": False, "index": i})
            continue
        temp = {"아이스": "ICE", "따뜻한": "HOT"}.get(m.group(1))
        options, packaging = [], False
        for part in (m.group(4) or "").split(","):
            part = part.strip()
            if not part:
                continue
            if part == "포장":
                packaging = True
                continue
            om = _OPT_COUNT.match(part)
            options.append({"name": om.group(1).strip(), "count": int(om.group(2) or 1)})
        parsed.append({"menu": m.group(2).strip(), "temperature": temp, "quantity": int(m.group(3) or 1),
                       "options": options, "packaging": packaging, "index": i})
    return parsed


def _opt_label(o: dict) -> str:
    return f"{o['name']} ×{o['count']}" if o.get("count", 1) > 1 else o["name"]


def _line_text(c: dict) -> str:
    temp = "아이스 " if c["temperature"] == "ICE" else "따뜻한 " if c["temperature"] == "HOT" else ""
    qty = f" ×{c['quantity']}" if c.get("quantity", 1) > 1 else ""
    extra = [_opt_label(o) for o in c.get("options", [])] + (["포장"] if c.get("packaging") else [])
    return f"{temp}{c['menu']}{qty}" + (f" ({', '.join(extra)})" if extra else "")


def _cart_text(cart: list) -> str:
    if not cart:
        return "장바구니가 비어 있어요."
    return "현재 장바구니: " + ", ".join(_line_text(c) for c in cart)


def _pick_lines(cart: list, target: str, t: str, target_temp: Optional[str], allow_every: bool = True):
    lines = [c for c in cart if c["menu"] == target]
    if target_temp:
        narrowed = [c for c in lines if c["temperature"] == target_temp]
        if narrowed:
            lines = narrowed
    if len(lines) <= 1:
        return lines, None
    if allow_every and _RE_EVERY.search(t):
        return lines, None
    if _RE_FIRST.search(t):
        return [lines[0]], None
    if _RE_LAST.search(t):
        return [lines[-1]], None
    listing = ", ".join(f"{n + 1}) {_line_text(c)}" for n, c in enumerate(lines))
    return [], (f"장바구니에 {_eun(target)} {len(lines)}줄 있어요. {listing}. "
                f"'처음 것', '마지막 것', '전부'처럼 말씀해 주세요.")


def _weak_cancel_applies(t: str) -> bool:
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

_PENDING: dict = {}
PENDING_TTL_SEC = 90
_RE_DISMISS = _rx(r"아니|됐어|됐아|그만|안할래|괜찮|그냥둬|그대로")
_RE_ORD_N = _rx(r"(\d+)번(?:째)?|(첫|두|세|네)번째")
_ORD_WORD = {"첫": 1, "두": 2, "세": 3, "네": 4}
_RE_PENDING_LAST = _rx(r"마지막|맨끝|나중|뒤에")
_RE_ORDER_TALK = _rx(r"주세요|주셔|줘|담아|주문|결제|계산")


def _set_pending(**kw) -> None:
    _PENDING.clear()
    _PENDING.update(kw, ts=time.time())


def clear_pending() -> None:
    _PENDING.clear()


def _resolve_pending(text, t, cart, menus, by_name, menu_names):
    if not _PENDING:
        return None
    if time.time() - _PENDING["ts"] > PENDING_TTL_SEC:
        _PENDING.clear()
        return None
    if len(t) > 16:
        return None
    p = dict(_PENDING)
    if _RE_DISMISS.search(t) and not extract_menu(text, menu_names):
        _PENDING.clear()
        return _result(p["intent"], "알겠어요. 장바구니는 그대로 둘게요.")

    if p["kind"] == "which_menu":
        target = extract_menu(text, menu_names)
        if target and target in [c["menu"] for c in cart] and not _RE_ORDER_TALK.search(t):
            _PENDING.clear()
            return detect_cart_command(f"{target} 취소해줘", [_cart_raw(c) for c in cart], menus)
        return None

    if p["kind"] == "pick_line":
        lines = [c for c in cart if c["menu"] == p["menu"]]
        if not lines:
            _PENDING.clear()
            return None
        chosen = None
        m = _RE_ORD_N.search(t)
        if m:
            n = int(m.group(1)) if m.group(1) else _ORD_WORD.get(m.group(2), 0)
            if 1 <= n <= len(lines):
                chosen = [lines[n - 1]]
        elif _RE_FIRST.search(t):
            chosen = [lines[0]]
        elif _RE_PENDING_LAST.search(t):
            chosen = [lines[-1]]
        elif p["verb"] == "cancel" and _RE_EVERY.search(t):
            chosen = lines
        else:
            temp = _temp_in(t)
            if temp:
                by_t = [c for c in lines if c["temperature"] == temp]
                if len(by_t) == 1:
                    chosen = by_t
        if not chosen:
            return None
        _PENDING.clear()
        if p["verb"] == "cancel":
            msg = (f"{_eul(p['menu'])} 모두 장바구니에서 뺐어요." if len(chosen) > 1
                   else f"'{_line_text(chosen[0])}' 줄을 장바구니에서 뺐어요.")
            return _result("cancel", msg, [{"type": "remove_line", "indexes": [c["index"] for c in chosen]}])
        return _set_options(p["t"], cart, p["menu"], None, p["details"], by_name, forced=chosen)
    return None


def _cart_raw(c: dict) -> str:
    return _line_text(c)


def _set_options(t, cart, target, target_temp, new_details, by_name, forced=None):
    if forced:
        picked, ask = forced, None
    else:
        picked, ask = _pick_lines(cart, target, t, target_temp, allow_every=False)
    if not picked:
        _set_pending(kind="pick_line", verb="set_options", menu=target, t=t, details=new_details, intent="modify")
        return _result("modify", ask)
    line = picked[0]
    info = by_name.get(target, {})
    order = {"menu": target, "temperature": line["temperature"] or "ICE", "option_details": [dict(d) for d in new_details]}
    _, notices = validate_options([order], [info] if info else [])
    kept = order["option_details"]
    if not kept:
        return _result("modify", " ".join(notices) or "적용할 수 있는 옵션이 없어요.")

    count = line["quantity"]
    pm = _RE_PART.search(t)
    if pm:
        g = pm.group(1)
        count = int(g) if g.isdigit() else _NUM_WORDS.get(g, 1)
    if count < 1 or count > line["quantity"]:
        return _result("modify", f"{_eun(target)} {line['quantity']}잔 담겨 있어요. 그 안에서 말씀해 주세요.")

    new_kinds = {d["kind"] for d in kept}
    keep_old = [o for o in line["options"] if _kind_of(o["name"]) not in new_kinds]
    options = keep_old + [{"name": d["name"], "count": d.get("count", 1)} for d in kept]
    rest = line["quantity"] - count
    msg = f"{target} {count}잔에 '{', '.join(_opt_label({'name': d['name'], 'count': d.get('count', 1)}) for d in kept)}' 옵션을 적용했어요."
    if rest:
        msg += f" 나머지 {rest}잔은 그대로예요."
    return _result("modify", " ".join([msg] + notices),
                   [{"type": "set_options", "index": line["index"], "count": count, "options": options}])

_KIND_PREFIX = (("샷", "shot"), ("시럽", "syrup"), ("크림", "cream"), ("휘핑", "cream"), ("연하게", "light"), ("사이즈", "size"))


def _kind_of(name: str) -> Optional[str]:
    for prefix, kind in _KIND_PREFIX:
        if name.startswith(prefix):
            return kind
    return None

_HOT_W = r"(?:핫|따뜻|따듯|따스|따숩|따땃|따끈|뜨끈|뜨듯|뜨신|뜨거|뜨겁|하시라고|하신대|하시래|하시다고|핫이)"
_ICE_W = r"(?:아이스|차갑|차가|시원|냉)"
_RE_NOT_ICE = re.compile(_ICE_W + r"\S{0,3}\s*(?:가\s*)?(?:아니|말고|싫|빼)")
_RE_NOT_HOT = re.compile(_HOT_W + r"\S{0,3}\s*(?:가\s*)?(?:아니|말고|싫|빼)")
_RE_TEMP_ALL = re.compile(r"(?:다|전부|모두|전체|죄다|다들|다\s*같이)\s*")
_RE_TEMP_VERB = re.compile(r"(?:바꿔|바꾸|변경|[해헤]\s*주|[해헤]\s*줘|로\s*줘|으로|라고|이라고|이래|하시|하신)")


def _temperature_all(t: str, cart: list, by_name: dict) -> Optional[dict]:
    if not cart or _RE_CANCEL_STRONG.search(t):
        return None
    hot_hit, ice_hit = re.search(_HOT_W, t), re.search(_ICE_W, t)
    if not (hot_hit or ice_hit):
        return None
    target = None
    if _RE_NOT_ICE.search(t):
        target = "HOT"
    elif _RE_NOT_HOT.search(t):
        target = "ICE"
    elif _RE_TEMP_ALL.search(t) and _RE_TEMP_VERB.search(t) and bool(hot_hit) != bool(ice_hit):
        target = "HOT" if hot_hit else "ICE"
    if not target:
        return None
    ok, skipped = [], []
    for name in dict.fromkeys(c["menu"] for c in cart):
        temps = by_name.get(name, {}).get("temps") or []
        (skipped if temps and target not in temps else ok).append(name)
    label = "따뜻한" if target == "HOT" else "아이스"
    if not ok:
        return _result("modify", f"장바구니의 메뉴는 {label} 음료로 주문할 수 없어요.")
    msg = f"장바구니를 모두 {label} 음료로 바꿨어요."
    if skipped:
        msg = f"{', '.join(ok)}만 {label} 음료로 바꿨어요. {', '.join(skipped)}은(는) {label} 음료로 주문할 수 없어요."
    return _result("modify", msg, [{"type": "set_temperature_all", "temperature": target, "menus": ok}])


def detect_cart_command(text: str, cart_items: list, menus: list) -> Optional[dict]:
    t = normalize_text(text)
    menu_names = [m["name"] for m in menus]
    by_name = {m["name"]: m for m in menus}
    cart = parse_cart(cart_items)
    cart_menus = [c["menu"] for c in cart]

    if _RE_POST_PAY.search(t):
        return _result(
            "cancel",
            "이미 결제한 주문은 키오스크에서 취소할 수 없어요. 카운터 직원에게 말씀해 주세요.",
        )

    resolved = _resolve_pending(text, t, cart, menus, by_name, menu_names)
    if resolved is not None:
        return resolved

    tall = None
    if not extract_menu(text, menu_names) or _RE_TEMP_ALL.search(t):
        tall = _temperature_all(t, cart, by_name)
    if tall is not None:
        return tall

    target0 = extract_menu(text, menu_names)
    target_temp0 = _temp_in(t)

    if (target0 and target0 in cart_menus and _RE_EXISTING.search(t)
            and not _RE_CANCEL_STRONG.search(t) and not _RE_CHANGE.search(t) and not _RE_REPLACE_SPLIT.search(t)):
        new_details = extract_option_details(text)
        if new_details:
            return _set_options(t, cart, target0, target_temp0, new_details, by_name)

    has_all = bool(_RE_ALL.search(t))
    menu_wide = has_all and bool(target0) and not _RE_CART_WIDE.search(t)
    if menu_wide:
        has_all = False
    has_cancel = bool(_RE_CANCEL_STRONG.search(t)) or _weak_cancel_applies(t) or bool(_RE_THAT.search(t))
    has_change = bool(_RE_CHANGE.search(t))
    has_replace = bool(_RE_REPLACE_SPLIT.search(t))

    if not (has_all or has_cancel or has_change or has_replace):
        return None

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
            return None

    if has_all:
        if not cart:
            return _result("cancel", "장바구니가 이미 비어 있어요.")
        return _result("cancel", "장바구니를 모두 비웠어요. 처음부터 다시 주문해 주세요.", [{"type": "remove_all"}])

    target, target_temp = target0, target_temp0

    if has_cancel:
        if not target and (_RE_LAST.search(t) or _RE_THAT.search(t)):
            if not cart:
                return _result("cancel", "장바구니가 비어 있어요.")
            last = cart[-1]
            return _result("cancel", f"방금 담은 {_eul(last['menu'])} 뺐어요.", [{"type": "remove_last"}])
        if target:
            if target not in cart_menus:
                return _result("cancel", f"장바구니에 {_eun(target)} 없어요. {_cart_text(cart)}")
            picked, ask = _pick_lines(cart, target, t, target_temp)
            if not picked:
                _set_pending(kind="pick_line", verb="cancel", menu=target, intent="cancel")
                return _result("cancel", ask)
            if len(picked) == len([c for c in cart if c["menu"] == target]) and len(picked) > 1:
                msg = f"{_eul(target)} 모두 장바구니에서 뺐어요."
            else:
                msg = f"'{_line_text(picked[0])}' 줄을 장바구니에서 뺐어요." if len(picked) == 1 else \
                      f"{_eul(target)} {len(picked)}줄 뺐어요."
            return _result("cancel", msg, [{"type": "remove_line", "indexes": [c["index"] for c in picked]}])
        if _RE_NON_CART.search(t):
            return None
        if not cart:
            return _result("cancel", "장바구니가 비어 있어요.")
        _set_pending(kind="which_menu", intent="cancel")
        return _result(
            "cancel",
            f"어떤 메뉴를 취소할까요? 전부 지우려면 '전부 취소'라고 말씀해 주세요. {_cart_text(cart)}",
        )

    if has_change:
        if _RE_MORE.search(t):
            return None
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
            stock = by_name.get(menu, {}).get("stock")
            if stock is not None:
                lines = [c for c in cart if c["menu"] == menu]
                others = sum(c["quantity"] for c in lines[:-1])
                if qty > stock - others:
                    return _result("modify", f"{_eun(menu)} 재고가 {stock}개뿐이라 {qty}개로 바꿀 수 없어요. {_cart_text(cart)}")
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
