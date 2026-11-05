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
from ai.order import OPTION_ALLOWED_CATEGORIES, _josa

DIALOG_ENABLED = os.getenv("KIO_DIALOG", "1") != "0"
AUTO_PAY = os.getenv("KIO_DIALOG_AUTO_PAY", "1") != "0"
# 사이즈 질문은 기본으로 끈다(화면에 사이즈 선택·가격 반영이 없어서). 필요하면 KIO_DIALOG_SIZE=1
ASK_SIZE = os.getenv("KIO_DIALOG_SIZE", "0") == "1"
MAX_RETRIES = 2  # 같은 질문을 이만큼 못 알아들으면 포기하고 기본값으로 진행

REQUIRED_SLOTS = ("temperature", "size")
OPTIONAL_SLOTS = ("shot", "syrup")
AMOUNT_SLOTS = {"shot_amount": "shot", "syrup_amount": "syrup"}  # 선택 옵션에 '네' 한 뒤 양을 묻는 후속 질문


def _rx(p: str) -> "re.Pattern":
    return re.compile(normalize_text(p))


_HOT = _rx(r"따뜻|뜨겁|뜨거|핫|뜨아|따아|하스|hot")
_ICE = _rx(r"아이스|차갑|차가|차게|시원|얼음|아아|ice")
_DEFAULT = _rx(r"그대로|기본|아무거나|상관없|아무나|알아서")
_SIZE_S = _rx(r"작은|작게|스몰|small|숏|^에스$|^s$")
_SIZE_M = _rx(r"보통|중간|미디엄|레귤러|medium|톨|^엠$|^m$")
_SIZE_L = _rx(r"큰|크게|라지|large|벤티|^엘$|^l$")
_YES = _rx(r"^(?:네|넵|예|응|어|그래|좋아|좋아요|추가|해줘|해주세요|할게|할게요|넣어|넣어줘|넣어주세요|부탁)")
_NO = _rx(r"아니|안해|안할|괜찮|됐|필요없|필요 없|없어|없이|그대로|빼|노$|싫")
_COUNT_WORDS = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4}
_SHOT_COUNT_ONLY = _rx(r"(\d+|한|하나|두|둘|세|셋|네|넷)(?:번|개|잔|샷)?(?:만)?(?:더)?(?:추가|넣|더)")
_AMOUNT_WORDS = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4, "더블": 2, "트리플": 3}
_SHOT_AMOUNT = _rx(r"(\d+|더블|트리플|하나|한|두|둘|세|셋|네|넷)")
_LV_HALF = _rx(r"절반|반만|반정도|하프")
_LV_LESS = _rx(r"적게|조금|약간|살짝|덜")
_LV_MORE = _rx(r"많이|듬뿍|넉넉|가득")
_LV_NORMAL = _rx(r"보통|기본|그냥|적당|알아서|중간")
_CANCEL = _rx(r"취소|그만|처음부터|주문안|안할래|다시할게")


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
    optional = [k for k in OPTIONAL_SLOTS if info.get("category") in OPTION_ALLOWED_CATEGORIES.get(k, set())]
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
        if slot in ("size", "shot", "syrup") and _has(order, slot):
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
        if hot == ice:  # 둘 다 말했거나 둘 다 없음
            if not hot and _DEFAULT.search(t):
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
    if slot in ("shot", "syrup"):
        details = [d for d in extract_option_details(text) if d.get("kind") == slot]
        if details:
            d = details[0]
            return "no" if d["name"].endswith("없음") else d
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
        queue.pop(0)
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
    if not any(missing_slots(o, by_name[o["menu"]]) for o in named):
        return None
    queue = [{"order": o, "asked": [], "pending": None, "retries": 0} for o in named]
    return _advance(queue, [], menus)


def answer_slot(state: dict, text: str, menus: list[dict],
                cart_items: Optional[list] = None, detect_command=None) -> Optional[dict]:
    """열려 있는 대화에 대한 사용자의 답을 처리한다.

    슬롯 답변이 아니면(새 메뉴 주문, 결제, 장바구니 명령 등) None을 돌려줘서
    기존 의도 분류 흐름이 이어받게 한다.
    """
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
    if extract_menu(text, list(by_name)):  # 새 메뉴를 말하면 새 주문으로 본다
        return None

    value = parse_answer(slot, text, info)
    if value is None:
        if detect_command is not None and detect_command(text, cart_items or [], menus):
            return None
        from ai.fast_intent import fast_classify
        if fast_classify(text, list(by_name)) in ("payment", "order_and_pay", "coupon", "recommend", "qa"):
            return None
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

    if slot in OPTIONAL_SLOTS and value == "yes":  # 얼마나 넣을지 이어서 묻는다
        head["pending"] = f"{slot}_amount"
        head["retries"] = 0
        answer = f"{P.ACK[slot]['yes']} {_question(head['pending'], order)}"
        return _result({"queue": queue}, [], answer)

    ack = _apply(order, slot, value)
    head["asked"].append(AMOUNT_SLOTS.get(slot, slot))
    return _advance(queue, [], menus, ack)
