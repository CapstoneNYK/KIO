"""슬롯 채우기 대화: 메뉴마다 빠진 옵션을 직원처럼 하나씩 되묻는다.

- 필수 옵션: 온도(HOT/ICE 둘 다 가능한 메뉴). 사이즈는 KIO_DIALOG_SIZE=1 일 때만
- 선택 옵션: 샷 추가, 시럽 (카테고리가 허용하는 메뉴만)
- 이미 말한 값은 건너뛰고, 필수 -> 선택 순서로 질문한다.
- 대화 상태는 서버에 저장하지 않고 프론트가 매 요청에 실어 보낸다.
- 돈·재고·상태가 걸린 판단이 아니라 순수 규칙이라 LLM을 쓰지 않는다.
"""
from __future__ import annotations

import os
import re
from typing import Optional

from ai import dialog_phrases as P
from ai.entity import extract_menu, extract_option_details, normalize_text
from ai.order import DIALOG_ASK_CATEGORIES, _josa

DIALOG_ENABLED = os.getenv("KIO_DIALOG", "1") != "0"
AUTO_PAY = os.getenv("KIO_DIALOG_AUTO_PAY", "1") != "0"
# 사이즈 질문은 기본으로 끈다(화면에 사이즈 선택·가격 반영이 없어서). 필요하면 KIO_DIALOG_SIZE=1
ASK_MORE = os.getenv("KIO_DIALOG_ASK_MORE", "1") != "0"  # 다 정한 뒤 바로 결제하지 않고 더 주문/요청사항을 묻는다
ASK_SIZE = os.getenv("KIO_DIALOG_SIZE", "0") == "1"
LITE_CUPS = 3  # 총 잔 수가 이 이상이면 선택 옵션(샷·연하게) 질문을 생략
MAX_RETRIES = 2  # 같은 질문을 이만큼 못 알아들으면 포기하고 기본값으로 진행

REQUIRED_SLOTS = ("temperature", "size")
OPTIONAL_SLOTS = ("shot", "light")  # 화면에서 실제로 고를 수 있는 옵션만 묻는다 (시럽·크림은 화면에 없음)
AMOUNT_SLOTS = {"shot_amount": "shot", "syrup_amount": "syrup"}  # 선택 옵션에 '네' 한 뒤 양을 묻는 후속 질문


def _rx(p: str) -> "re.Pattern":
    return re.compile(normalize_text(p))


_HOT = _rx(r"따뜻|따듯|따스|따숩|따땃|따끈|뜨끈|뜨듯|뜨신|뜨겁|뜨거|핫|뜨아|따아|하스|hot")
_ICE = _rx(r"아이스|차갑|차가|차게|차거|찬거|찬걸|찬것|찬음료|찬물|찬커피|시원|얼음|아아|ice")
_DEFAULT = _rx(r"그대로|기본|아무거나|상관없|아무나|알아서")
_SIZE_S = _rx(r"작은|작게|스몰|small|숏|^에스$|^s$")
_SIZE_M = _rx(r"보통|중간|미디엄|레귤러|medium|톨|^엠$|^m$")
_SIZE_L = _rx(r"큰|크게|라지|large|벤티|^엘$|^l$")
_YES = _rx(r"^(?:네|넵|예|응|어|그래|좋아|좋아요|추가|해줘|해주세요|할게|할게요|넣어|넣어줘|넣어주세요|부탁)")
_NO = _rx(r"아니|아뇨|아녀|아녜|안해|안할|안할래|괜찮|됐|필요없|필요 없|없어|없이|그대로|빼|노$|싫|안넣|넣지마|하지마")
_COUNT_WORDS = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4}
_SHOT_COUNT_ONLY = _rx(r"(\d+|한|하나|두|둘|세|셋|네|넷)(?:번|개|잔|샷)?(?:만)?(?:더)?(?:추가|넣|더)")
_AMOUNT_WORDS = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4, "더블": 2, "트리플": 3}
_SHOT_AMOUNT = _rx(r"(\d+|더블|트리플|하나|한|두|둘|세|셋|네|넷)")
_LV_HALF = _rx(r"절반|반만|반정도|하프")
_LV_LESS = _rx(r"적게|조금|약간|살짝|덜")
_LV_MORE = _rx(r"많이|듬뿍|넉넉|가득")
_LV_NORMAL = _rx(r"보통|기본|그냥|적당|알아서|중간")
_NEG_WORD = _rx(r"말고|아니라|아닌|빼고|싫")
_CANCEL = _rx(r"취소|그만|처음부터|주문안|안할래|다시할게|안먹|안마시|안마실|안시킬|안시켜|안할게|그냥갈")
_REPEAT = _rx(r"다시|뭐라고|뭐라구|뭐요|뭐라|못들|안들려|안들리|한번더|천천히|잠깐|잠시|기다려|잠만")
_FILLER_ONLY = re.compile(r"^(?:[음어아으에엥흠]+[.…~!]*|(?:네|예|응|어|엥|뭐)\?+)$")  # "음...", "네?" — 대답이 아니라 되묻거나 생각하는 소리
_QUESTION = _rx(r"\?|있나요|뭐예요|뭐에요|얼마|어디|언제|왜|어떻게|뭐가|뭐있|몇|무슨|어떤|되나요|돼요|뭐야")
_COUNT_ONLY = _rx(r"^(\d+|한|하나|두|둘|세|셋)(?:번|개|잔|샷)?(?:만)?(?:이?요)?$")


# ---------------------------------------------------------------------------
# 1단계: 메뉴가 요구하는 옵션 (필수/선택) — 기존 메뉴 데이터(temps, sizes, category)에서 계산
# ---------------------------------------------------------------------------
def option_spec(info: dict) -> dict:
    temps = info.get("temps") or []
    sizes = info.get("sizes") or []
    required = []
    if len(temps) > 1:
        required.append("temperature")
    if ASK_SIZE and len(sizes) > 1:
        required.append("size")
    optional = [k for k in OPTIONAL_SLOTS if info.get("category") in DIALOG_ASK_CATEGORIES.get(k, set())]
    return {"required": required, "optional": optional}


def _has(order: dict, kind: str) -> bool:
    return any(d.get("kind") == kind for d in order.get("option_details", []))


def missing_slots(order: dict, info: dict, asked: Optional[list] = None) -> list[str]:
    """아직 정해야 할 옵션 목록 (필수 먼저, 그다음 선택)."""
    spec = option_spec(info)
    asked = asked or []
    out = []
    for slot in spec["required"] + spec["optional"]:
        if slot in asked:
            continue
        if slot == "temperature" and order.get("temp_explicit"):
            continue
        if slot in ("size", "shot", "light", "syrup") and _has(order, slot):
            continue
        out.append(slot)
    return out


# ---------------------------------------------------------------------------
# 사용자의 짧은 답변 해석
# ---------------------------------------------------------------------------
def parse_answer(slot: str, text: str, info: dict) -> Optional[object]:
    """슬롯 답변을 값으로 바꾼다. 못 알아들으면 None."""
    t = normalize_text(text)
    if not t:
        return None
    if slot == "temperature":
        temps = info.get("temps") or []
        hot, ice = bool(_HOT.search(t)), bool(_ICE.search(t))
        if hot and ice:  # "따뜻한 거 말고 차가운 걸로" — 아닌 쪽을 빼고 고른다
            neg = _NEG_WORD.search(t)
            hm, im = _HOT.search(t), _ICE.search(t)
            if neg and hm.start() < neg.start() < im.start():
                return "ICE"
            if neg and im.start() < neg.start() < hm.start():
                return "HOT"
            return None
        if hot == ice:  # 둘 다 없음
            if _DEFAULT.search(t):
                return "ICE" if "ICE" in temps else temps[0]
            return None
        return "HOT" if hot else "ICE"
    if slot == "size":
        sizes = info.get("sizes") or []
        found = [s for s, rx in (("S", _SIZE_S), ("M", _SIZE_M), ("L", _SIZE_L)) if rx.search(t)]
        if len(found) == 1 and found[0] in sizes:
            return found[0]
        if not found and _DEFAULT.search(t):
            return "M" if "M" in sizes else sizes[0]
        return None
    if slot in AMOUNT_SLOTS and re.match(r"^(?:아니|아뇨|아녀|괜찮|됐|안해|안할|필요없|싫)", t):
        return "no"  # '몇 샷이요?'에 '아니요' — 추가하지 않는 것으로 본다
    if slot == "shot_amount":
        if _DEFAULT.search(t) or _LV_NORMAL.search(t):
            return 1
        m = _SHOT_AMOUNT.search(t)
        if not m:
            return None
        g = m.group(1)
        n = int(g) if g.isdigit() else _AMOUNT_WORDS.get(g, 1)
        return n if 1 <= n <= 5 else None
    if slot == "syrup_amount":
        return _syrup_level(t)
    if slot == "light":
        if _NO.search(t):
            return "no"
        if _YES.search(t) or extract_option_details(text):
            return "yes"
        return None
    if slot in ("shot", "syrup"):
        details = [d for d in extract_option_details(text) if d.get("kind") == slot]
        if details:
            d = details[0]
            return "no" if d["name"].endswith("없음") else d
        if slot == "shot":
            m = _COUNT_ONLY.match(t)  # "두 번이요"처럼 바로 횟수만 말한 경우도 '네' + 횟수로 본다
            if m:
                g = m.group(1)
                n = int(g) if g.isdigit() else _COUNT_WORDS.get(g, 1)
                if 1 <= n <= 5:
                    return {"kind": "shot", "name": "샷추가", "count": n}
        if slot == "shot":  # "두 번 추가해주세요"처럼 '샷'을 빼고 횟수만 말하는 경우
            m = _SHOT_COUNT_ONLY.search(t)
            if m:
                g = m.group(1)
                n = int(g) if g.isdigit() else _COUNT_WORDS.get(g, 1)
                return {"kind": "shot", "name": "샷추가", "count": n}
        if slot == "syrup" and not _NO.search(t):  # "네 많이"처럼 한 번에 말한 경우
            level = _syrup_level(t)
            if level:
                return level
        if _NO.search(t):
            return "no"
        if _YES.search(t):
            return "yes"
        return None
    return None


_PART = _rx(r"(\d+|한|하나|두|둘|세|셋)(?:잔|개|컵)?(?:은|는|만)")
_PLAIN = _rx(r"기본|그대로|보통|없이|안해|아니|빼고|일반")


def _split_count(text: str, qty: int) -> Optional[int]:
    """"한 잔은 연하게, 다른 한 잔은 기본으로"처럼 일부 수량에만 옵션을 걸었으면 그 수량을 돌려준다."""
    if qty < 2:
        return None
    t = normalize_text(text)
    ms = list(_PART.finditer(t))
    for i, m in enumerate(ms):
        seg = t[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(t)]
        if _PLAIN.search(seg):
            continue
        g = m.group(1)
        n = int(g) if g.isdigit() else _COUNT_WORDS.get(g, 1)
        if 0 < n < qty:
            return n
    return None


def _temp_split(text: str, qty: int) -> Optional[tuple[int, int]]:
    """"한 잔은 따뜻하게 한 잔은 차갑게" — 잔마다 온도를 다르게 말했으면 (따뜻한 잔 수, 아이스 잔 수)."""
    if qty < 2:
        return None
    t = normalize_text(text)
    ms = list(_PART.finditer(t))
    if len(ms) < 2:
        return None
    hot_n = ice_n = 0
    for i, m in enumerate(ms):
        seg = t[m.end(): ms[i + 1].start() if i + 1 < len(ms) else len(t)]
        g = m.group(1)
        n = int(g) if g.isdigit() else _COUNT_WORDS.get(g, 1)
        h, c = bool(_HOT.search(seg)), bool(_ICE.search(seg))
        if h == c:
            return None
        if h:
            hot_n += n
        else:
            ice_n += n
    return (hot_n, ice_n) if hot_n and ice_n and hot_n + ice_n == qty else None


def _syrup_level(t: str) -> Optional[dict]:
    for rx, name in ((_LV_HALF, "시럽 절반"), (_LV_LESS, "시럽 적게"), (_LV_MORE, "시럽 많이"), (_LV_NORMAL, "시럽 추가")):
        if rx.search(t):
            return {"kind": "syrup", "name": name, "count": 1}
    return None


def _apply(order: dict, slot: str, value) -> str:
    """값을 주문에 반영하고 짧은 확인 문구를 돌려준다."""
    if slot == "temperature":
        order["temperature"] = value
        order["temp_explicit"] = True
        return P.ACK["temperature"][value]
    if slot == "size":
        order.setdefault("option_details", []).append({"kind": "size", "name": f"사이즈 {value}", "count": 1})
        order["options"] = [d["name"] for d in order["option_details"]]
        return P.ACK["size"][value]
    if slot == "shot_amount":
        order.setdefault("option_details", []).append({"kind": "shot", "name": "샷추가", "count": value})
        order["options"] = [d["name"] for d in order["option_details"]]
        return P.SHOT_AMOUNT_ACK.format(n=value)
    if slot == "syrup_amount":
        order.setdefault("option_details", []).append(value)
        order["options"] = [d["name"] for d in order["option_details"]]
        return P.SYRUP_AMOUNT_ACK.get(value["name"], P.ACK["syrup"]["yes"])
    if slot == "light":
        if value == "no":
            return P.ACK["light"]["no"]
        order.setdefault("option_details", []).append({"kind": "light", "name": "연하게", "count": 1})
        order["options"] = [d["name"] for d in order["option_details"]]
        return P.ACK["light"]["yes"]
    if slot in ("shot", "syrup"):
        if value == "no":
            return P.ACK[slot]["no"]
        detail = value if isinstance(value, dict) else (
            {"kind": "shot", "name": "샷추가", "count": 1} if slot == "shot"
            else {"kind": "syrup", "name": "시럽 추가", "count": 1})
        order.setdefault("option_details", []).append(detail)
        order["options"] = [d["name"] for d in order["option_details"]]
        return P.ACK[slot]["yes"]
    return ""


# ---------------------------------------------------------------------------
# 대화 진행
# ---------------------------------------------------------------------------
def _qty_text(q: int) -> str:
    words = {1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯"}
    return f"{words.get(q, str(q))} 잔"


def _describe(order: dict) -> str:
    parts = [("아이스" if order["temperature"] == "ICE" else "따뜻한") + f" {order['menu']}"]
    extras = []
    for d in order.get("option_details", []):
        extras.append(f"{d['name']} ×{d['count']}" if d.get("count", 1) > 1 else d["name"])
    if order.get("packaging"):
        extras.append("포장")
    text = parts[0] + f" {_qty_text(order.get('quantity', 1))}"
    return text + (f" ({', '.join(extras)})" if extras else "")


def _question(slot: str, order: dict, retry: bool = False) -> str:
    if retry:
        return P.REASK[slot]
    return P.QUESTIONS[slot].format(menu=_josa(order["menu"], "은", "는"))


def _result(state, orders, answer, go_payment=False, done=False):
    return {"state": state, "orders": orders, "answer": answer, "go_payment": go_payment, "done": done}


def _advance(queue: list, completed: list, menus: list[dict], prefix: str = "") -> dict:
    """큐 맨 앞 주문의 다음 질문을 만들고, 다 끝난 주문은 completed로 옮긴다."""
    by_name = {m["name"]: m for m in menus}
    notes = [prefix] if prefix else []
    lite_seen = False
    while queue:
        head = queue[0]
        order = head["order"]
        info = by_name.get(order["menu"], {})
        todo = missing_slots(order, info, head["asked"])
        if todo:
            slot = todo[0]
            head["pending"] = slot
            head["retries"] = 0
            lead = ""
            if completed and not head["asked"]:
                lead = P.NEXT_MENU.format(menu=order["menu"]) + " "
            answer = " ".join(notes + [lead + _question(slot, order)]).strip()
            return _result({"queue": queue}, completed, answer)
        notes.append(P.ADDED.format(items=_describe(order)))
        completed.append(order)
        lite_seen = lite_seen or head.get("lite", False)
        queue.pop(0)
    if lite_seen:
        notes.append(P.OPTIONS_ON_SCREEN)
    if ASK_MORE:  # 바로 결제로 넘어가지 않고 더 주문할 메뉴나 요청사항이 있는지 묻는다
        return _result({"queue": [], "stage": "more", "last": [o for o in completed[-1:]]}, completed,
                       " ".join(notes + [P.ASK_MORE]).strip())
    tail = P.FINISH_PAY if AUTO_PAY else P.FINISH_MORE
    return _result(None, completed, " ".join(notes + [tail]).strip(), go_payment=AUTO_PAY, done=True)


def start_dialog(orders: list[dict], menus: list[dict]) -> Optional[dict]:
    """주문들에 빠진 옵션이 있으면 첫 질문을 만든다. 질문할 게 없으면 None."""
    if not DIALOG_ENABLED:
        return None
    by_name = {m["name"]: m for m in menus}
    named = [o for o in orders if o.get("menu") and o["menu"] in by_name]
    if not named:
        return None
    # 메뉴가 여럿이거나 총 3잔 이상이면 질문이 길어지므로 꼭 필요한 것(온도)만 묻는다.
    lite = len(named) >= 2 or sum(o.get("quantity", 1) for o in named) >= LITE_CUPS
    skip = list(OPTIONAL_SLOTS) if lite else []
    if not any(missing_slots(o, by_name[o["menu"]], skip) for o in named):
        return None
    queue = [{"order": o, "asked": list(skip), "pending": None, "retries": 0, "lite": lite}
             for o in named]
    return _advance(queue, [], menus)


_AGAIN = _rx(r"(?:(한|하나|두|둘|세|셋|네|넷|\d+)(?:잔|개|컵)?|똑같은거|같은거|아까거|그거|이거)(?:만)?(?:더|또)|똑같은(?:거|걸)|같은(?:거|걸)로|또한")
_AGAIN_COUNT = _rx(r"(한|하나|두|둘|세|셋|네|넷|\d+)(?:잔|개|컵)?(?:만)?(?:더|또)")
_DONE = _rx(r"^(?:아니|아뇨|없|괜찮|됐|그게다|이게다|다예요|다됐|끝|그만|결제|계산|이대로|그대로|충분|그거면|네그게다|응그게다)")
_DONE_ANY = _rx(r"없어요|없습니다|없는데|없어|그게다|이게다|이대로|결제할게|결제해|괜찮아|됐어요|됐습니다|끝이에요|끝났어")


def _answer_more(state: dict, text: str, menus: list[dict], cart_items, detect_command) -> Optional[dict]:
    """주문을 다 정한 뒤 '더 주문할 메뉴나 요청사항 있으세요?'에 대한 답을 처리한다."""
    by_name = {m["name"]: m for m in menus}
    t = normalize_text(text)
    if not t:
        return None
    if _CANCEL.search(t) or extract_menu(text, list(by_name)):
        return None  # 취소나 새 메뉴는 기존 흐름이 처리
    last = (state.get("last") or [None])[-1]
    m = _AGAIN.search(t)
    if last and m and not _DONE.search(t):  # "하나 더 주세요", "똑같은 걸로" — 방금 담은 것을 그대로 더 담는다
        mc = _AGAIN_COUNT.search(t)
        g = mc.group(1) if mc else None
        n = (int(g) if g.isdigit() else _COUNT_WORDS.get(g, 1)) if g else 1
        n = max(1, min(n, 9))
        again = dict(last, quantity=n)
        msg = P.AGAIN_ADDED.format(item=_describe(again))
        return _result({"queue": [], "stage": "more", "last": [again]}, [again], f"{msg} {P.ASK_MORE_SHORT}")
    if _DONE.search(t) or _DONE_ANY.search(t):
        return _result(None, [], P.FINISH_PAY, go_payment=True, done=True)
    if detect_command is not None and detect_command(text, cart_items or [], menus):
        return None
    from ai.fast_intent import fast_classify
    if fast_classify(text, list(by_name)) in ("payment", "order_and_pay", "coupon", "recommend", "qa", "order"):
        return None
    if _YES.search(t) and len(t) <= 6:  # "네"만 말하면 무엇인지 묻는다
        return _result({"queue": [], "stage": "more"}, [], P.MORE_WHICH)
    memo = re.sub(r"\s+", " ", text).strip()[:60]
    res = _result({"queue": [], "stage": "more"}, [], P.MEMO_SAVED.format(memo=memo))
    res["memo"] = memo
    return res


def current_question(state: Optional[dict]) -> str:
    """열려 있는 대화가 지금 기다리는 질문 (질문·추천에 답한 뒤 다시 이어 붙이는 용도)."""
    if not state:
        return ""
    if state.get("stage") == "more":
        return P.ASK_MORE_SHORT
    queue = state.get("queue") or []
    if not queue or not queue[0].get("pending"):
        return ""
    return _question(queue[0]["pending"], queue[0]["order"])


def _finish_with_defaults(queue: list, menus: list[dict]) -> dict:
    """아직 묻는 중에 결제를 말했을 때: 안 정한 필수 옵션은 기본값(아이스)으로 담고 결제로 간다."""
    by_name = {m["name"]: m for m in menus}
    defaulted = []
    for h in queue:
        order = h["order"]
        info = by_name.get(order["menu"], {})
        for slot in missing_slots(order, info, h["asked"]):
            if slot in REQUIRED_SLOTS:
                value = parse_answer(slot, "그대로", info)
                _apply(order, slot, value)
                if slot == "temperature":
                    defaulted.append(order["menu"])
        h["asked"] = list({*h["asked"], *OPTIONAL_SLOTS, *REQUIRED_SLOTS})
    res = _advance(queue, [], menus)
    note = f"온도를 말씀하지 않으셔서 {', '.join(defaulted)}는 아이스로 담았어요. " if defaulted else ""
    res["answer"] = note + res["answer"].replace(P.ASK_MORE, "").strip() + " " + P.FINISH_PAY
    res["state"], res["go_payment"], res["done"] = None, True, True
    return res


_CHANGE_CUE = _rx(r"아니|말고|바꿔|바꿀|바꾸|로할래|로할게|로할께|로하겠|로주세요|로줘")
_PARTICLE = "는은이가를을도로으만요"
_HAS_QTY = re.compile(r"(\d+|한|하나|두|둘|세|셋|네|넷|다섯)\s*(?:잔|개|컵)")


def _refers_to(text: str, menu: str) -> bool:
    """말 속의 단어가 지금 정하는 메뉴 이름의 일부인지 ("라떼는" → 바닐라라떼)."""
    name = normalize_text(menu)
    for w in re.findall(r"[가-힣]+", text):
        w = w.rstrip(_PARTICLE) or w
        if len(w) >= 2 and normalize_text(w) in name:
            return True
    return False


_ALL_WORD = _rx(r"둘다|셋다|모두|전부|다같이|다(?=따뜻|따듯|아이스|뜨겁|차갑|시원|핫)|같은걸로|똑같이")


def _answer_temps(queue: list, text: str, t: str, by_name: dict, menus: list) -> Optional[dict]:
    """메뉴가 여럿일 때 한 번에 답하는 경우: "둘 다 따뜻하게", "아메리카노는 아이스 라떼는 따뜻하게"."""
    waiting = [h for h in queue if "temperature" in missing_slots(
        h["order"], by_name.get(h["order"]["menu"], {}), h["asked"])]
    if len(waiting) < 2:
        return None

    def supports(h, v):
        temps = by_name.get(h["order"]["menu"], {}).get("temps") or []
        return not temps or v in temps

    hot, ice = bool(_HOT.search(t)), bool(_ICE.search(t))
    picked: dict[int, str] = {}
    if _ALL_WORD.search(t) and hot != ice:
        v = "HOT" if hot else "ICE"
        for h in waiting:
            if supports(h, v):
                picked[id(h)] = v
    else:
        cur = None
        for w in re.findall(r"[가-힣]+", text):
            base = w.rstrip(_PARTICLE) or w
            for h in waiting:
                if id(h) not in picked and len(base) >= 2 and normalize_text(base) in normalize_text(h["order"]["menu"]):
                    cur = h
                    break
            wn = normalize_text(w)
            v = "HOT" if _HOT.search(wn) and not _ICE.search(wn) else "ICE" if _ICE.search(wn) and not _HOT.search(wn) else None
            if v and cur is not None and id(cur) not in picked and supports(cur, v):
                picked[id(cur)] = v
                cur = None
    if not picked:
        return None
    acks = []
    for h in waiting:
        if id(h) in picked:
            _apply(h["order"], "temperature", picked[id(h)])
            acks.append(f"{h['order']['menu']} {'따뜻하게' if picked[id(h)] == 'HOT' else '차갑게'}")
    return _advance(queue, [], menus, ", ".join(acks) + " 알겠어요.")


def _temp_fix(order: dict, info: dict, t: str) -> Optional[str]:
    """명시적인 온도 말('아이스로', '따뜻한 걸로')이 지금 온도와 다르면 바꾸고 안내 문구를 돌려준다."""
    hot, ice = bool(_HOT.search(t)), bool(_ICE.search(t))
    if hot == ice:
        return None
    new = "HOT" if hot else "ICE"
    temps = info.get("temps") or []
    if (temps and new not in temps) or order.get("temperature") == new or not order.get("temp_explicit"):
        return None
    order["temperature"] = new
    return P.ACK["temperature"][new]


def _swap_menu(state: dict, text: str, new_menu: str, by_name: dict, menus: list) -> dict:
    """묻는 도중 다른 메뉴로 바꾸겠다고 하면 지금 주문의 메뉴만 갈아끼우고 처음부터 다시 묻는다."""
    queue = state["queue"]
    head = queue[0]
    order = head["order"]
    old = order["menu"]
    order["menu"] = new_menu
    order["option_details"], order["options"] = [], []
    m = _HAS_QTY.search(text)
    if m:
        g = m.group(1)
        order["quantity"] = int(g) if g.isdigit() else _COUNT_WORDS.get(g, order.get("quantity", 1))
    temps = by_name[new_menu].get("temps") or []
    order["temp_explicit"] = len(temps) == 1
    if len(temps) == 1:
        order["temperature"] = temps[0]
    head["asked"] = list(OPTIONAL_SLOTS) if head.get("lite") else []
    head["retries"] = 0
    ack = P.MENU_SWAPPED.format(new=new_menu)
    return _advance(queue, [], menus, ack)


def answer_slot(state: dict, text: str, menus: list[dict],
                cart_items: Optional[list] = None, detect_command=None) -> Optional[dict]:
    """열려 있는 대화에 대한 사용자의 답을 처리한다.

    슬롯 답변이 아니면(새 메뉴 주문, 결제, 장바구니 명령 등) None을 돌려줘서
    기존 의도 분류 흐름이 이어받게 한다.
    """
    if (state or {}).get("stage") == "more":
        return _answer_more(state, text, menus, cart_items, detect_command)
    queue = (state or {}).get("queue") or []
    if not queue:
        return None
    by_name = {m["name"]: m for m in menus}
    head = queue[0]
    order, slot = head["order"], head.get("pending")
    info = by_name.get(order["menu"], {})
    if not slot:
        return None

    t = normalize_text(text)
    if _CANCEL.search(t):
        return _result(None, [], P.CANCELLED, done=True)
    if slot == "temperature" and len(queue) >= 2:
        multi = _answer_temps(queue, text, t, by_name, menus)
        if multi is not None:
            return multi
    mentioned = extract_menu(text, list(by_name))
    if mentioned and _refers_to(text, order["menu"]):
        mentioned = None  # "라떼는 따뜻하게"처럼 지금 정하는 메뉴를 가리키는 말
    if mentioned and mentioned != order["menu"]:
        if not _CHANGE_CUE.search(t):  # 새 메뉴를 말하면 새 주문으로 본다
            return None
        return _swap_menu(state, text, mentioned, by_name, menus)  # "아니 아메리카노로 할래" — 메뉴를 바꾼다

    if slot == "temperature" and order.get("quantity", 1) >= 2:
        split = _temp_split(text, order["quantity"])
        if split:  # 잔마다 온도가 다르면 주문을 둘로 나누고, 이 경우 선택 옵션은 묻지 않는다
            import copy
            hot_n, ice_n = split
            skip = list(OPTIONAL_SLOTS)
            rest = copy.deepcopy(order)
            order["temperature"], order["quantity"], order["temp_explicit"] = "HOT", hot_n, True
            rest["temperature"], rest["quantity"], rest["temp_explicit"] = "ICE", ice_n, True
            head["asked"] = list({*head["asked"], "temperature", *skip})
            head["lite"] = True
            queue.insert(1, {"order": rest, "asked": ["temperature", *skip], "pending": None, "retries": 0, "lite": True})
            return _advance(queue, [], menus, P.TEMP_SPLIT_ACK.format(hot=hot_n, ice=ice_n))

    if slot != "temperature":  # 샷·연하게를 묻는 중에 "아니 아이스로"처럼 온도를 고치는 경우
        fixed = _temp_fix(order, info, t)
        if fixed:
            return _result({"queue": queue}, [], f"{fixed} {_question(slot, order)}")

    pre = ""
    if slot == "temperature":  # "샷 추가해서 따뜻하게"처럼 묻기 전에 먼저 말한 옵션은 바로 반영
        allowed = option_spec(info)["optional"]
        got = [d for d in extract_option_details(text)
               if d.get("kind") in allowed and not _has(order, d["kind"])]
        for d in got:
            order.setdefault("option_details", []).append(d)
            head["asked"].append(d["kind"])
        if got:
            order["options"] = [d["name"] for d in order["option_details"]]
            pre = " ".join(P.ACK[d["kind"]]["yes"] for d in got)

    if _FILLER_ONLY.match(t):  # "음...", "네?"는 대답으로 세지 않고 질문만 다시 들려 준다
        return _result({"queue": queue}, [], _question(slot, order))

    value = parse_answer(slot, text, info)
    if value is None:
        if detect_command is not None and detect_command(text, cart_items or [], menus):
            return None
        from ai.fast_intent import fast_classify
        kind = fast_classify(text, list(by_name))
        if kind in ("payment", "order_and_pay"):  # 아직 정하는 중에 결제를 말하면 기본값으로 담고 결제로 간다
            return _finish_with_defaults(queue, menus)
        if kind in ("coupon", "recommend", "qa", "order") or _QUESTION.search(t):
            return None  # 질문·추천 등은 기존 흐름이 답하고, 대화는 main 이 이어 붙인다
        if _REPEAT.search(t):  # "뭐라고요?"·"다시 말해줘"·"잠깐만요"는 못 알아들은 게 아니라 다시 들려 달라는 뜻
            return _result({"queue": queue}, [], _question(slot, order))
        if pre:  # 온도를 정하기 전에 샷·연하게부터 말한 경우: 반영하고 온도만 다시 묻는다
            return _result({"queue": queue}, [], f"{pre} {_question(slot, order)}")
        head["retries"] = head.get("retries", 0) + 1
        if head["retries"] < MAX_RETRIES:
            return _result({"queue": queue}, [], _question(slot, order, retry=True))
        if slot in AMOUNT_SLOTS:  # 이미 '네'라고 했으니 기본 양으로 진행
            default = 1 if slot == "shot_amount" else {"kind": "syrup", "name": "시럽 추가", "count": 1}
            ack = _apply(order, slot, default)
            head["asked"].append(AMOUNT_SLOTS[slot])
            return _advance(queue, [], menus, ack)
        if slot in OPTIONAL_SLOTS:  # 선택 옵션은 '없음'으로 진행
            head["asked"].append(slot)
            return _advance(queue, [], menus, P.SKIP_OPTIONAL)
        # 필수 옵션: 기본값으로 담고 화면에서 바꾸도록 안내
        default = parse_answer(slot, "그대로", info)
        label = {"temperature": "아이스" if default == "ICE" else "따뜻하게",
                 "size": f"사이즈 {default}"}[slot]
        _apply(order, slot, default)
        head["asked"].append(slot)
        return _advance(queue, [], menus, P.FALLBACK_DEFAULT.format(value=label))

    if slot in AMOUNT_SLOTS.values() and value == "yes":  # 얼마나 넣을지 이어서 묻는다
        head["pending"] = f"{slot}_amount"
        head["retries"] = 0
        answer = f"{P.ACK[slot]['yes']} {_question(head['pending'], order)}"
        return _result({"queue": queue}, [], answer)

    n = _split_count(text, order.get("quantity", 1)) if slot in ("shot", "light") and value != "no" else None
    if n:
        # 일부 수량에만 옵션 적용: 주문을 둘로 나눈다 (옵션 있는 쪽 먼저, 나머지는 이 옵션을 다시 묻지 않음)
        import copy
        rest = copy.deepcopy(order)
        rest["quantity"] = order["quantity"] - n
        order["quantity"] = n
        queue.insert(1, {"order": rest, "asked": list(head["asked"]) + [slot], "pending": None, "retries": 0})
    if slot in AMOUNT_SLOTS and value == "no":
        head["asked"].append(AMOUNT_SLOTS[slot])
        return _advance(queue, [], menus, P.ACK[AMOUNT_SLOTS[slot]]["no"])
    ack = _apply(order, slot, value)
    if pre:
        ack = f"{pre} {ack}"
    head["asked"].append(AMOUNT_SLOTS.get(slot, slot))
    return _advance(queue, [], menus, ack)
