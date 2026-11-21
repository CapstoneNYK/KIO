# [cart_command.py] 이미 담긴 장바구니를 말로 고치는 명령(취소·수량 변경·온도 변경·옵션 변경·교체)을 감지·처리한다.
# 진입점은 detect_cart_command(): 명령이 아니면 None 을 돌려 주문/질문 흐름이 이어받게 한다.
# 반환값은 {intent, answer, cart_actions:[…]} — cart_actions 를 프론트가 실제 장바구니에 반영한다.
import re
import time
from contextvars import ContextVar
from typing import Optional

from ai.entity import extract_menu, extract_option_details, extract_packaging
from ai.vocab import HOT_CORE, HOT_EXTRA_CART, ICE_CORE, ICE_EXTRA_CART
from ai.korean import NUM_WORDS_10, has_final as _has_final, normalize_text, rx as _rx, rx_keep, to_int, unify_ae_e
from ai.order import validate_options



# ──── 장바구니 명령 감지용 정규식 ────
# 결제 '후' 취소/환불 요청 → 키오스크에서는 불가, 직원 안내
_RE_POST_PAY = _rx(r"(결제|계산|주문)(?:을|를)?(?:한|했|된|완료|끝).{0,8}(취소|환불)|환불")
# '전부 취소/장바구니 비워/처음부터' — 장바구니 전체 삭제 표현
_RE_ALL = _rx(
    r"(?:다|전부|전체|모두|싹|주문|장바구니)(?:를|을|은|는|다)?(?:다)?"
    r"(?:취소|삭제|지워|지우|비워|비우|초기화|리셋)|처음부터|다시시작|전부빼|다빼|모두빼"
)
# '방금/마지막/아까 것' (뒤쪽 줄 선택), 아래 _RE_FIRST 는 '처음/첫' (앞쪽 줄 선택)
_RE_LAST = _rx(r"(방금|마지막|아까|조금전|금방)(?:것|거|껀|걸|담은|넣은)?")
_RE_FIRST = _rx(r"처음|먼저|첫|맨처음|제일처음")
# '전부/모두/전체' — 같은 메뉴가 여러 줄일 때 전부 대상으로 삼는 표현
_RE_EVERY = _rx(r"전부|모두|전체|싹|다(?=취소|빼|삭제|지워|지우|없애)")
# '주문/장바구니/처음부터' — 특정 메뉴가 아니라 장바구니 전체를 가리키는 말
_RE_CART_WIDE = _rx(r"주문|장바구니|처음부터|다시시작")
# '담은/시킨/장바구니에 있는' — 이미 담긴 것을 가리키는 표현
_RE_EXISTING = _rx(r"담은|담아둔|시킨|넣은|주문한|담긴|장바구니|있는|방금|아까|처음에")
# '하나는/두 잔만' 처럼 일부 수량을 가리키는 표현. [겹침] dialog._PART, entity._UNIT_START 와 같은 역할
_RE_PART = _rx(r"(\d+|한|하나|두|둘|세|셋|네|넷)(?:개|잔)?(?:는|만|은)")
# '아메리카노 중에 하나 샷 추가' — 담긴 것 중 일부만 가리키는 표현(수량이 group 1)
_RE_PART_IN = _rx(r"중(?:에서|에)?(\d+|한|하나|두|둘|세|셋|네|넷)(?:개|잔)?(?:을|를|만)?")


# '하나는'/'중에 하나' 형태의 부분 수량 표현을 말한 순서대로 모은다(겹치면 앞의 것만)
def _part_matches(t: str) -> list:
    found = sorted(list(_RE_PART.finditer(t)) + list(_RE_PART_IN.finditer(t)), key=lambda m: m.start())
    out: list = []
    for m in found:
        if not out or m.start() >= out[-1].end():
            out.append(m)
    return out
# '한 잔 빼줘/두 잔 줄여' — 수량을 일부만 줄이는 표현
_RE_MINUS_N = _rx(r"(\d+|한|하나|두|둘|세|셋)(?:잔|개|컵)(?:만|은|는)?(?:빼|취소|줄여|줄이|덜)")
# '그거 취소해줘' — 지시어로 가리키는 취소
_RE_THAT = _rx(r"(?:그거|그건|이거|이건|그걸|이걸)(?:는|은)?(?:좀)?(?:취소|빼|삭제|지워)")

# 취소어: 강한 것(취소·삭제·지워 …)은 그 자체로 취소로 본다.
# 약한 것('빼')은 '시럽 빼줘'처럼 옵션을 빼는 말일 수 있어서 _weak_cancel_applies() 로 따로 걸러낸다.
# [겹침] dialog._CANCEL 에도 비슷한 취소 표현 목록이 있다.
_RE_CANCEL_STRONG = _rx(r"취소|삭제|지워|지우|제거|필요없|안마실|안할래|안먹")
_RE_CANCEL_WEAK = _rx(r"빼줘|빼주|빼요|빼고싶|빼버려|빼자|빼라|빼")
# '빼' 앞에 이 단어(시럽·샷·얼음…)가 있으면 메뉴 취소가 아니라 옵션 빼기로 본다
_OPTION_WORDS = tuple(normalize_text(w) for w in ("시럽", "크림", "샷", "얼음", "휘핑", "우유", "설탕", "토핑", "연하게"))

# 옵션(우유 종류·시럽·샷 …) 변경 표현. _RE_CHANGE 는 '바꿔/변경/수정' 같은 변경 동사
_RE_OPTION_CHANGE = _rx(r"우유|두유|오트|귀리|아몬드|저지방|무지방|시럽|샷|크림|휘핑|설탕|얼음|토핑")
_RE_CHANGE = _rx(r"바꿔|바꾸|바꿀|바꿔줘|변경|수정|고쳐|줄여|늘려")
# 'A 말고 B', 'A 대신 B' — 메뉴 교체 표현
_RE_REPLACE_SPLIT = _rx(r"말고|대신")

# 숫자 표현 / 숫자 단어 변환표.
# [겹침] entity.QUANTITY_MAP, entity._NUM_WORDS, entity._UNIT_NUM, dialog._COUNT_WORDS, preference._NUM_WORDS 와 같은 표를 각자 따로 들고 있다.
_NUM = r"(\d+|한|하나|두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)"
_NUM_WORDS = NUM_WORDS_10
# 수량 변경 표현('두 개로 바꿔'). _RE_MORE('하나 더')는 '추가 주문'이라 수량 변경이 아니다.
_RE_QTY = _rx(_NUM + r"(?:(?:개|잔|병)(?:만|으로|로)?|(?:으로|로|만))(?:바꿔|변경|수정|해줘|해주세요|줄여|늘려|할게|만)?")
_RE_MORE = _rx(r"(?:\d+|한|하나|두|둘|세|셋|네|넷)(?:개|잔|병)?더")
# 온도 표현. [겹침] 이 파일 아래의 _HOT_W/_ICE_W, dialog._HOT/_ICE, preference._RE_HOT/_RE_ICE 와 단어 목록이 조금씩 다르다
#        (예: 여기 _RE_ICE 에는 '얼음'·'아아'가 없고, _ICE_W 에는 '냉'이 있음)
_RE_HOT = _rx("|".join([HOT_CORE, HOT_EXTRA_CART]))
_RE_ICE = _rx("|".join([ICE_CORE, ICE_EXTRA_CART]))

# '결제/카드/쿠폰/할인…' 이 들어 있으면 장바구니 명령이 아니라 결제 쪽 말로 본다
_RE_NON_CART = _rx(r"결제|카드|쿠폰|계산|카카오|네이버|할인|상품권|멤버십")

# 수량 변경 최대치
MAX_QTY = 20


# 단어 + 을/를. [겹침] order._josa() 가 같은 기능(조사 붙이기)을 따로 구현하고 있다.
def _eul(word: str) -> str:
    return f"{word}{'을' if _has_final(word) else '를'}"


# 단어 + 은/는 ([겹침] order._josa 와 동일 기능)
def _eun(word: str) -> str:
    return f"{word}{'은' if _has_final(word) else '는'}"

# 프론트가 보내는 장바구니 한 줄 문자열 파싱 정규식. 예: '아이스 아메리카노 ×2 (샷추가, 포장)'
_CART_LINE = re.compile(r"^(?:(아이스|따뜻한) )?(.+?)(?: ×(\d+))?(?: \((.*)\))?$")
_OPT_COUNT = re.compile(r"^(.*?)(?: ×(\d+))?$")


# 장바구니 문자열 목록 → [{menu, temperature, quantity, options, packaging, index}] 로 변환
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


# 옵션 한 개를 '샷추가 ×2' 형태 문자열로
def _opt_label(o: dict) -> str:
    return f"{o['name']} ×{o['count']}" if o.get("count", 1) > 1 else o["name"]


# 장바구니 한 줄 dict → 사용자에게 읽어 주는 문자열로
def _line_text(c: dict) -> str:
    temp = "아이스 " if c["temperature"] == "ICE" else "따뜻한 " if c["temperature"] == "HOT" else ""
    qty = f" ×{c['quantity']}" if c.get("quantity", 1) > 1 else ""
    extra = [_opt_label(o) for o in c.get("options", [])] + (["포장"] if c.get("packaging") else [])
    return f"{temp}{c['menu']}{qty}" + (f" ({', '.join(extra)})" if extra else "")


# 장바구니 전체를 '현재 장바구니: …' 문장으로
def _cart_text(cart: list) -> str:
    if not cart:
        return "장바구니가 비어 있어요."
    return "현재 장바구니: " + ", ".join(_line_text(c) for c in cart)


# 같은 메뉴가 여러 줄일 때 어느 줄을 대상으로 할지 결정. 온도로 좁힘 → '전부' → '처음/마지막' 순.
# 그래도 못 정하면 (빈 목록, 되묻는 문장)을 돌려 사용자가 고르게 한다.
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


# 약한 취소어('빼')가 정말 메뉴 취소인지 판단 — 바로 앞 6글자에 옵션 단어가 있으면 옵션 빼기라서 제외
def _weak_cancel_applies(t: str) -> bool:
    for m in _RE_CANCEL_WEAK.finditer(t):
        before = t[max(0, m.start() - 6):m.start()]
        if not any(w in before for w in _OPTION_WORDS):
            return True
    return False


# 문장에서 온도(HOT/ICE)를 뽑는다. 둘 다 있으면 '말고' 로 부정된 쪽을 버리고 나머지를 선택
def _temp_in(text_norm: str) -> Optional[str]:
    hot, ice = bool(_RE_HOT.search(text_norm)), bool(_RE_ICE.search(text_norm))
    if hot and not ice:
        return "HOT"
    if ice and not hot:
        return "ICE"
    if hot and ice:  # "따뜻한 거 말고 차가운 걸로" — 부정된 쪽이 아닌 온도를 고른다
        if _RE_NOT_HOT.search(text_norm) and not _RE_NOT_ICE.search(text_norm):
            return "ICE"
        if _RE_NOT_ICE.search(text_norm) and not _RE_NOT_HOT.search(text_norm):
            return "HOT"
    return None


# 이 파일의 공통 반환 형식 {intent, answer, cart_actions}
def _result(intent: str, answer: str, actions: Optional[list] = None) -> dict:
    return {"intent": intent, "answer": answer, "cart_actions": actions or []}

# '어느 메뉴/어느 줄이요?' 되묻기 상태를 임시로 저장(90초 유효).
# 세션(키오스크) 번호별로 따로 저장한다. session_id 를 안 넘기면 "" 하나만 쓰므로 예전처럼 서버 전체가 하나를 공유한다.
_PENDING_STORE: dict[str, dict] = {}
_SID: ContextVar[str] = ContextVar("cart_command_sid", default="")
PENDING_TTL_SEC = 90
# 되묻기에 대한 '아니/됐어/그대로' — 하던 걸 그만두는 표현
_RE_DISMISS = _rx(r"아니|됐어|됐아|그만|안할래|괜찮|그냥둬|그대로")
# '2번', '첫번째' — 되묻기에서 몇 번째 줄인지 고르는 표현. [겹침] fast_intent._RE_ORDINAL, entity.ORDINAL_KEYWORDS
_RE_ORD_N = _rx(r"(\d+)번(?:째)?|(첫|두|세|네)번째")
_ORD_WORD = {"첫": 1, "두": 2, "세": 3, "네": 4}
_RE_PENDING_LAST = _rx(r"마지막|맨끝|나중|뒤에")
# 주문/결제 말투 — 되묻기 답변이 아니라 새 주문으로 보이는 경우를 걸러냄. [겹침] fast_intent._RE_ORDER_VERB 과 비슷
_RE_ORDER_TALK = _rx(r"주세요|주셔|줘|담아|주문|결제|계산")


# 지금 처리 중인 세션의 되묻기 상태 dict (없으면 빈 dict 를 만들어 돌려줌)
def _pending() -> dict:
    return _PENDING_STORE.setdefault(_SID.get(), {})


# 오래된 세션의 되묻기 상태를 정리(키오스크가 많아져도 메모리가 계속 늘지 않게)
def _prune_pending() -> None:
    now = time.time()
    for sid in [k for k, v in _PENDING_STORE.items() if not v or now - v.get("ts", 0) > PENDING_TTL_SEC]:
        del _PENDING_STORE[sid]


# 되묻기 상태 저장(이전 상태는 덮어씀)
def _set_pending(**kw) -> None:
    _prune_pending()
    p = _pending()
    p.clear()
    p.update(kw, ts=time.time())


# 되묻기 상태 비우기. session_id 를 주면 그 세션만, 안 주면 전부(예전 동작)
def clear_pending(session_id: Optional[str] = None) -> None:
    if session_id is None:
        _PENDING_STORE.clear()
    else:
        _PENDING_STORE.pop(session_id, None)


# 이전에 되묻기를 했고(90초 이내) 이번 말이 그 답이면 처리한다. 종류(kind):
#   which_menu : '어떤 메뉴를 취소할까요?' → 메뉴 이름이 나오면 취소 실행
#   pick_line  : '어느 줄이요?' → 번호/처음/마지막/온도로 줄을 골라 취소 또는 옵션 적용
def _resolve_pending(text, t, cart, menus, by_name, menu_names):
    pending = _pending()
    if not pending:
        return None
    if time.time() - pending["ts"] > PENDING_TTL_SEC:
        pending.clear()
        return None
    if len(t) > 16:
        return None
    p = dict(pending)
    if _RE_DISMISS.search(t) and not extract_menu(text, menu_names):
        pending.clear()
        return _result(p["intent"], "알겠어요. 장바구니는 그대로 둘게요.")

    if p["kind"] == "which_menu":
        target = extract_menu(text, menu_names)
        if target and target in [c["menu"] for c in cart] and not _RE_ORDER_TALK.search(t):
            pending.clear()
            return _detect_cart_command(f"{target} 취소해줘", [_cart_raw(c) for c in cart], menus)  # 같은 세션 안에서 다시 호출
        return None

    if p["kind"] == "pick_line":
        lines = [c for c in cart if c["menu"] == p["menu"]]
        if not lines:
            pending.clear()
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
        pending.clear()
        if p["verb"] == "cancel":
            msg = (f"{_eul(p['menu'])} 모두 장바구니에서 뺐어요." if len(chosen) > 1
                   else f"'{_line_text(chosen[0])}' 줄을 장바구니에서 뺐어요.")
            return _result("cancel", msg, [{"type": "remove_line", "indexes": [c["index"] for c in chosen]}])
        return _set_options(p["t"], cart, p["menu"], None, p["details"], by_name, forced=chosen)
    return None


# 장바구니 줄을 다시 문자열로 되돌림(_line_text 와 동일)
def _cart_raw(c: dict) -> str:
    return _line_text(c)


# 담긴 메뉴에 옵션(샷·연하게 등)을 적용. 줄 선택 → 메뉴가 허용하는 옵션만 남김(validate_options) →
# 일부 수량만 지정했으면 그 수량만 적용 → set_options 액션 생성
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
        count = to_int(g, _NUM_WORDS, 1)
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

# '연하게 한 아이스 아메리카노에는 시럽 추가해주세요' — 메뉴 앞에서 '이미 그 옵션이 붙은 줄'을 가리키고, 뒤에서 새로 더할 옵션을 말한 경우
#  (줄, 새 옵션들)을 돌려준다. 같은 메뉴가 2줄 이상이고 가리킨 줄이 하나로 정해질 때만, 아니면 None
_RE_DESCRIBES = _rx(r"(?:한|해둔|해놓은|된|넣은|들어간|붙은|있는|추가한|추가된)(?:아이스|따뜻한|핫|차가운)?$")


def _line_by_option_description(text: str, t: str, cart: list, target: Optional[str], target_temp: Optional[str]):
    if not target:
        return None
    lines = [c for c in cart if c["menu"] == target]
    if len(lines) < 2:
        return None
    name = normalize_text(target)
    pos = t.find(name)
    if pos <= 0:
        return None
    prefix, after = t[:pos], t[pos + len(name):]
    if not _RE_DESCRIBES.search(prefix):
        return None
    described = extract_option_details(prefix)
    new_details = extract_option_details(after)
    if not described or not new_details:
        return None
    kinds = {d["kind"] for d in described}
    matched = [c for c in lines if kinds <= {_kind_of(o["name"]) for o in c["options"]}]
    if target_temp:
        matched = [c for c in matched if c["temperature"] == target_temp] or matched
    return (matched[0], new_details) if len(matched) == 1 else None


# 옵션 이름 앞글자로 종류(shot/syrup/cream/light/size) 판별용 표
_KIND_PREFIX = (("샷", "shot"), ("시럽", "syrup"), ("크림", "cream"), ("휘핑", "cream"), ("연하게", "light"), ("사이즈", "size"))


# 옵션 이름 → 종류
def _kind_of(name: str) -> Optional[str]:
    for prefix, kind in _KIND_PREFIX:
        if name.startswith(prefix):
            return kind
    return None

# 온도 단어 + 부정 표현('아이스 아니고', '뜨거운 건 싫어'). [겹침] 위 _RE_HOT/_RE_ICE 와 별도 목록(여기에만 '하시라고/냉' 등이 있음)
_HOT_W = unify_ae_e(r"(?:핫|따뜻|따듯|따스|따숩|따땃|따끈|뜨끈|뜨듯|뜨신|뜨거|뜨겁|하시라고|하신대|하시래|하시다고|핫이)")
_ICE_W = unify_ae_e(r"(?:아이스|차갑|차가|시원|냉)")
_RE_NOT_ICE = rx_keep(_ICE_W + r"\S{0,3}\s*(?:가\s*)?(?:아니|말고|싫|빼)")
_RE_NOT_HOT = rx_keep(_HOT_W + r"\S{0,3}\s*(?:가\s*)?(?:아니|말고|싫|빼)")
_RE_TEMP_ALL = re.compile(r"(?:다|전부|모두|전체|죄다|다들|다\s*같이)\s*")
_RE_TEMP_VERB = rx_keep(r"(?:바꿔|바꾸|변경|[해헤]\s*주|[해헤]\s*줘|로\s*줘|으로|라고|이라고|이래|하시|하신)")


# '다 아이스로 바꿔', '뜨거운 거 아니고 차갑게' — 장바구니 전체 온도 변경. 메뉴가 그 온도를 지원하는지 확인해 ok/skipped 로 나눔
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


# '아메리카노 하나는 연하게 하나는 샷 추가' — 같은 줄의 잔마다 다른 옵션을 나눠 적용
def _options_by_parts(text: str, t: str, cart: list, target: Optional[str], target_temp: Optional[str],
                      by_name: dict) -> Optional[dict]:
    """"아메리카노 하나는 연하게 하나는 샷 추가해줘" — 같은 줄의 잔마다 다른 요청사항을 나눠 적용한다."""
    if not target or not cart or _RE_CANCEL_STRONG.search(t):
        return None
    parts = _part_matches(t)
    # '샷 추가 해주고 하나는 연하게' — 수량 없이 앞에 말한 옵션은 '나머지 잔'에 적용한다(lead)
    lead = extract_option_details(t[:parts[0].start()]) if len(parts) == 1 else None
    # '아이스 아메리카노 한 잔은 시럽 추가' — 한 부분만 말해도 담긴 그 메뉴의 그만큼에만 옵션을 적용한다
    # (이 경우 새로 담는 게 아니라 담긴 메뉴 수정이어야 하므로 장바구니에 그 메뉴가 있을 때만)
    if len(parts) < 2 and not lead and (not parts or target not in [c["menu"] for c in cart]):
        return None
    segments = []
    for i, pm in enumerate(parts):
        end = parts[i + 1].start() if i + 1 < len(parts) else len(t)
        details = extract_option_details(t[pm.end():end])
        if not details:
            return None
        g = pm.group(1)
        segments.append((to_int(g, _NUM_WORDS, 1), details))
    picked, _ = _pick_lines(cart, target, t, target_temp, allow_every=False)
    if len(picked) != 1:
        return None
    line = picked[0]
    if lead:
        left = line["quantity"] - sum(n for n, _ in segments)
        if left < 1:
            return None
        segments.insert(0, (left, lead))
    if sum(n for n, _ in segments) > line["quantity"]:
        return _result("modify", f"{_eun(target)} {line['quantity']}잔 담겨 있어요. 그 안에서 말씀해 주세요.")
    info = by_name.get(target, {})
    actions, said, notices = [], [], []
    for n, details in segments:
        order = {"menu": target, "temperature": line["temperature"] or "ICE", "option_details": [dict(d) for d in details]}
        _, ns = validate_options([order], [info] if info else [])
        notices += ns
        kept = order["option_details"]
        if not kept:
            return _result("modify", " ".join(ns) or "적용할 수 있는 옵션이 없어요.")
        new_kinds = {d["kind"] for d in kept}
        options = [o for o in line["options"] if _kind_of(o["name"]) not in new_kinds] + \
                  [{"name": d["name"], "count": d.get("count", 1)} for d in kept]
        actions.append({"type": "set_options", "index": line["index"], "count": n, "options": options})
        said.append(f"{n}잔에는 '{', '.join(_opt_label({'name': d['name'], 'count': d.get('count', 1)}) for d in kept)}'")
    msg = f"{target} {', '.join(said)} 옵션을 적용했어요."
    rest = line["quantity"] - sum(n for n, _ in segments)
    if rest:
        msg += f" 나머지 {rest}잔은 그대로예요."
    return _result("modify", " ".join([msg] + notices), actions)


# '아메리카노 하나만 따뜻하게' — 같은 줄의 일부 수량만 온도 변경
def _temperature_part(text: str, t: str, cart: list, menu: Optional[str], by_name: dict) -> Optional[dict]:
    """"아메리카노 하나는 따뜻하게" — 같은 메뉴 줄의 일부 수량만 온도를 바꾼다."""
    if not menu or menu not in [c["menu"] for c in cart] or _RE_CANCEL_STRONG.search(t):
        return None
    pm = _RE_PART.search(t)
    if not pm:
        return None
    target = _temp_in(t[pm.end():])  # "아이스 아메리카노 하나는 연하게"의 앞쪽 '아이스'는 메뉴를 가리키는 말이다
    if not target:
        return None
    g = pm.group(1)
    count = to_int(g, _NUM_WORDS, 1)
    lines = [c for c in cart if c["menu"] == menu]
    line = lines[-1]
    temps = by_name.get(menu, {}).get("temps") or []
    label = "따뜻한" if target == "HOT" else "아이스"
    if temps and target not in temps:
        return _result("modify", f"{_eun(menu)} {label} 음료로 주문할 수 없어요.")
    if count < 1 or count > line["quantity"]:
        return _result("modify", f"{_eun(menu)} {line['quantity']}잔 담겨 있어요. 그 안에서 말씀해 주세요.")
    if line["temperature"] == target:
        return _result("modify", f"{_eun(menu)} 이미 {label} 음료예요.")
    msg = f"{menu} {count}잔을 {label} 음료로 바꿨어요."
    rest = line["quantity"] - count
    if rest:
        msg += f" 나머지 {rest}잔은 그대로예요."
    return _result("modify", msg, [{"type": "set_temperature_part", "menu": menu, "temperature": target, "count": count}])


# '그냥 차갑게 줘'처럼 온도를 고쳐 말하는 표현
_RE_TEMP_CORRECT = _rx(
    r"(?:차갑|차게|시원하|따뜻하|따듯하|뜨겁|뜨거)게?(?:줘|주세요|줄래|할게|할래|해줘|해주세요|해주라|해요)"
    r"|(?:아이스|핫)(?:로|으로)(?:줘|주세요|줄래|할게|할래|해줘|해주세요|해요)")
_RE_NEW_QTY = _rx(r"\d+(?:잔|개|컵)|[한두세네다섯]잔|[한두세네]개|하나|둘|셋|넷|더")


# 담아 둔 메뉴를 '아니다 그냥 차갑게 줘'로 고쳐 말하면 새 주문이 아니라 온도 변경으로 처리(수량 말이 있으면 새 주문으로 봄)
# [겹침] _temperature_all / _temperature_part / 이 함수 + dialog._temp_fix 가 모두 '온도 바꾸기'를 다루므로 호출 순서가 중요함(detect_cart_command 참고)
def _temperature_correction(t: str, target: Optional[str], temp: Optional[str], cart: list, by_name: dict) -> Optional[dict]:
    """"아니다 디카페인 라떼 그냥 차갑게 줘" — 담아 둔 메뉴를 다른 온도로 달라고 고쳐 말하면 온도를 바꾼다(새 주문이 아니다)."""
    if not target or not temp or not _RE_TEMP_CORRECT.search(t) or _RE_NEW_QTY.search(t) or _RE_CANCEL_STRONG.search(t):
        return None
    lines = [c for c in cart if c["menu"] == target]
    if not lines:
        return None
    differing = [c for c in lines if c["temperature"] != temp]
    if len(differing) != len(lines) or len(lines) != 1:
        return None
    temps = by_name.get(target, {}).get("temps") or []
    label = "아이스" if temp == "ICE" else "따뜻한"
    if temps and temp not in temps:
        only = "아이스" if "ICE" in temps else "따뜻한"
        return _result("modify", f"{_eun(target)} {only} 음료로만 주문할 수 있어요.")
    return _result("modify", f"{_eul(target)} {label} 음료로 바꿨어요.",
                   [{"type": "set_temperature", "menu": target, "temperature": temp}])


# 메뉴 없이 '포장할게요/여기서 먹을게요'만 말한 경우
def _packaging_only(text: str, t: str, menu_names: list) -> Optional[dict]:
    """"가지고 갈게", "포장할게요", "여기서 먹을게요"처럼 메뉴 없이 먹고가기/가져가기만 말한 경우."""
    if len(t) > 16 or re.search(r"\d", t) or _RE_NON_CART.search(t) or extract_menu(text, menu_names):
        return None
    packaging = extract_packaging(text)
    if packaging is None:
        return None
    msg = "가져가시는 걸로 알겠어요. 주문 확인에서 가져가기를 골라 주세요." if packaging else \
          "매장에서 드시는 걸로 알겠어요. 주문 확인에서 먹고가기를 골라 주세요."
    return _result("modify", msg, [{"type": "set_packaging", "packaging": packaging}])


# 장바구니 명령 감지 메인 함수. 검사 순서(= 우선순위):
#  1) 결제 후 취소/환불 → 직원 안내
#  2) 이전 되묻기에 대한 답(_resolve_pending)
#  3) 포장/매장만 말한 경우
#  4) '한 잔 빼줘' (수량 일부 감소)
#  5) 전체 온도 변경 → 일부 수량 온도 → 잔별 옵션 → 온도 정정
#  6) 담긴 메뉴에 옵션 추가('아메리카노 샷 추가')
#  7) 취소어/변경어/교체어/전체삭제 중 하나라도 있는지 판정 → 없으면 None
#  8) 교체('A 말고 B') → 전체 삭제 → 취소 → 변경(수량/온도) 순으로 처리
# 명령이 아니면 None.
def detect_cart_command(text: str, cart_items: list, menus: list, session_id: str = "") -> Optional[dict]:
    """장바구니 명령 감지. session_id 는 키오스크(세션)별 되묻기 상태를 분리하기 위한 값(안 주면 하나를 공유)."""
    token = _SID.set(session_id)
    try:
        return _detect_cart_command(text, cart_items, menus)
    finally:
        _SID.reset(token)


def _detect_cart_command(text: str, cart_items: list, menus: list) -> Optional[dict]:
    t = normalize_text(text)
    menu_names = [m["name"] for m in menus]
    by_name = {m["name"]: m for m in menus}
    cart = parse_cart(cart_items)
    cart_menus = [c["menu"] for c in cart]

    # [1] 이미 결제한 주문은 키오스크에서 취소 불가
    if _RE_POST_PAY.search(t):
        return _result(
            "cancel",
            "이미 결제한 주문은 키오스크에서 취소할 수 없어요. 카운터 직원에게 말씀해 주세요.",
        )

    # [2] 직전 되묻기에 대한 답이면 여기서 끝
    resolved = _resolve_pending(text, t, cart, menus, by_name, menu_names)
    if resolved is not None:
        return resolved

    # [3] 포장/매장 선택만 말한 경우
    pack_only = _packaging_only(text, t, menu_names)
    if pack_only is not None:
        return pack_only

    # [4] '한 잔 빼줘' — 줄이 하나(또는 메뉴를 말함)면 그만큼만 줄이고, 수량 이상이면 아예 제거
    minus = _RE_MINUS_N.search(t)
    if minus and cart:  # "한 잔 빼줘" — 장바구니 줄이 하나(또는 메뉴를 말함)면 그만큼만 줄인다
        want = extract_menu(text, menu_names)
        lines = [c for c in cart if not want or c["menu"] == want]
        if len(lines) == 1:
            line = lines[0]
            g = minus.group(1)
            n = to_int(g, _NUM_WORDS, 1)
            if n >= line["quantity"]:
                return _result("cancel", f"{_eul(line['menu'])} 장바구니에서 뺐어요.",
                               [{"type": "remove_item", "menu": line["menu"], "temperature": line["temperature"]}])
            left = line["quantity"] - n
            return _result("modify", f"{_eul(line['menu'])} {left}개로 줄였어요.",
                           [{"type": "set_quantity", "menu": line["menu"], "quantity": left,
                             "temperature": line["temperature"]}])

    # [5-a] 메뉴 이름 없이 말했거나 '다 …' 표현이면 장바구니 전체 온도 변경인지 먼저 확인
    tall = None
    if not extract_menu(text, menu_names) or _RE_TEMP_ALL.search(t):
        tall = _temperature_all(t, cart, by_name)
    if tall is not None:
        return tall

    # 이후 공통으로 쓸 값: 말한 메뉴 / 말한 온도
    target0 = extract_menu(text, menu_names)
    target_temp0 = _temp_in(t)

    # [5-b] 일부 수량만 온도 변경
    part = _temperature_part(text, t, cart, target0, by_name)
    if part is not None:
        return part

    # [5-c] 잔별로 다른 옵션 적용. 메뉴를 안 말해도('샷 추가 해주고 하나는 연하게') 2잔 이상 담긴 가장 최근 줄에 적용한다
    parts_target = target0
    if not target0 and _part_matches(t):
        multi = [c for c in cart if c["quantity"] >= 2]
        if multi:
            parts_target = multi[-1]["menu"]
    by_parts = _options_by_parts(text, t, cart, parts_target, target_temp0, by_name)
    if by_parts is not None:
        return by_parts

    # [5-d] 온도 정정
    corrected = _temperature_correction(t, target0, target_temp0, cart, by_name)
    if corrected is not None:
        return corrected

    # [5-e] '연하게 한 아이스 아메리카노에는 시럽 추가' — 같은 메뉴가 여러 줄이면 이미 가진 옵션으로 줄을 가리키고 새 옵션을 더한다
    described = _line_by_option_description(text, t, cart, target0, target_temp0)
    if described is not None:
        line, new_details = described
        return _set_options(t, cart, target0, target_temp0, new_details, by_name, forced=[line])

    # [6] 담긴 메뉴를 가리키며 옵션을 말하면 옵션 변경('방금 담은 아메리카노 샷 추가')
    if (target0 and target0 in cart_menus and _RE_EXISTING.search(t)
            and not _RE_CANCEL_STRONG.search(t) and not _RE_CHANGE.search(t) and not _RE_REPLACE_SPLIT.search(t)):
        new_details = extract_option_details(text)
        if new_details:
            return _set_options(t, cart, target0, target_temp0, new_details, by_name)

    # [7] 이 말이 어떤 종류의 명령인지 플래그로 정리: 전체삭제 / 취소 / 변경 / 교체
    #     (특정 메뉴를 말하면서 '다 취소'라고 하면 장바구니 전체가 아니라 그 메뉴만 대상)
    has_all = bool(_RE_ALL.search(t))
    menu_wide = has_all and bool(target0) and not _RE_CART_WIDE.search(t)
    if menu_wide:
        has_all = False
    has_cancel = bool(_RE_CANCEL_STRONG.search(t)) or _weak_cancel_applies(t) or bool(_RE_THAT.search(t))
    has_change = bool(_RE_CHANGE.search(t))
    has_replace = bool(_RE_REPLACE_SPLIT.search(t))

    # 아무 명령 표현도 없으면 이 함수의 대상이 아님
    if not (has_all or has_cancel or has_change or has_replace):
        return None

    # [8-a] 'A 말고 B' 교체: 담긴 A 를 빼고 B 를 담음(B 품절이면 안내)
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

    # [8-b] 장바구니 전체 비우기
    if has_all:
        if not cart:
            return _result("cancel", "장바구니가 이미 비어 있어요.")
        return _result("cancel", "장바구니를 모두 비웠어요. 처음부터 다시 주문해 주세요.", [{"type": "remove_all"}])

    # [8-c] 이후는 취소 / 변경 처리에 쓸 대상 메뉴·온도
    target, target_temp = target0, target_temp0

    # [8-c] 취소: 메뉴 없이 '방금 거 취소' → 마지막 줄 / 메뉴가 있으면 줄 선택 후 제거(여러 줄이면 되묻기) / 아무 대상도 없으면 '어떤 메뉴를 취소할까요?'
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

    # [8-d] 변경: '하나 더'는 변경이 아니라 추가 주문 → None / 옵션 변경은 여기서 처리 안 함 /
    #        수량 변경(재고·최대 수량 검사) 또는 온도 변경(메뉴가 지원하는 온도인지 검사)
    if has_change:
        if _RE_MORE.search(t):
            return None
        qty_match = _RE_QTY.search(t)
        if not qty_match and _RE_OPTION_CHANGE.search(t):
            return None  # "아이스 딸기라떼 우유는 저지방으로 바꿔줘" — 온도가 아니라 요청사항
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
            qty = to_int(g, _NUM_WORDS, 1)
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
