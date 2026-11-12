"""어르신 주문 시나리오 시뮬레이터.

프론트(SpeechInput)가 하는 일(장바구니 반영, 대화 상태 되돌려 보내기, 결제 이동)을 흉내 내서
/api/ask 처리 함수(main._handle_ask)에 여러 발화를 차례로 보내 보고, 대화 전체와 최종 장바구니를 보여준다.

  python -m eval.sim_elder            # LLM 없이(규칙 경로 + 주문 말버릇 어림 분류, 질문·추천 답변은 '[LLM필요]')
  python -m eval.sim_elder --llm      # 실제 Ollama LLM 사용
  python -m eval.sim_elder -v         # 모든 대화 출력 (기본은 실패한 시나리오만)
  python -m eval.sim_elder --cafe     # 카페 손님 유형별 시나리오만 (sim_scenarios_cafe.py)
"""
import asyncio
import sys
import tempfile
from pathlib import Path

from app.admin import db as admin_db

USE_LLM = "--llm" in sys.argv
VERBOSE = "-v" in sys.argv

if "--live" not in sys.argv:
    admin_db.DB_PATH = Path(tempfile.mkdtemp()) / "sim.db"
admin_db.init_db()

import main  # noqa: E402
from ai.cart_command import clear_pending  # noqa: E402

LLM_NEEDED = "[LLM필요]"
if not USE_LLM:
    import re as _re
    # LLM 대신 쓰는 어림 분류: 주문 말버릇이 있으면 order, 아니면 qa (규칙으로 안 잡힌 발화만 여기로 온다)
    _ORDER_HINT = _re.compile(r"주세요|주세여|주쇼|주라|줘|줄래|달라|부탁|하나|[한두세네]\s*[잔개]|\d\s*[잔개번]")
    main.classify_intent = lambda q: "order" if _ORDER_HINT.search(q) else "qa"

    class _StubChain:
        def invoke(self, *_a, **_k):
            return LLM_NEEDED

    main.qa_chain = _StubChain()

    class _Rec:
        answer, menus = LLM_NEEDED, []

    main._recommend = lambda q: _Rec()
main.log_interaction = lambda *a, **k: None
main.log_intent_query = lambda *a, **k: None


class Kiosk:
    """프론트 상태: 장바구니, 대화 상태, 요청사항 메모, 결제 이동 여부."""

    def __init__(self):
        self.cart: list[dict] = []
        self.dialog = None
        self.memo = ""
        self.paid = False
        self.log: list[tuple[str, str]] = []
        clear_pending()
        main._last_asked.clear()
        main._pending_temp.clear()
        main._last_recommended_menus.clear()

    # --- 프론트가 서버로 보내는 장바구니 문자열
    def cart_items(self) -> list[str]:
        out = []
        for i in self.cart:
            extra = [(f"{o['name']} ×{o['count']}" if o["count"] > 1 else o["name"]) for o in i["options"]]
            if i.get("packaging"):
                extra.append("포장")
            out.append(("아이스" if i["temp"] == "ICE" else "따뜻한") + f" {i['menu']}"
                       + (f" ×{i['qty']}" if i["qty"] > 1 else "") + (f" ({', '.join(extra)})" if extra else ""))
        return out

    def _add(self, menu, temp, qty, options, packaging=False):
        key = (menu, temp, packaging, sorted((o["name"], o["count"]) for o in options))
        for i in self.cart:
            if (i["menu"], i["temp"], i.get("packaging", False), sorted((o["name"], o["count"]) for o in i["options"])) == key:
                i["qty"] += qty
                return
        self.cart.append({"menu": menu, "temp": temp, "qty": qty, "options": options, "packaging": packaging})

    def _lines(self, menu, temp=None):
        return [i for i in self.cart if i["menu"] == menu and (not temp or i["temp"] == temp)]

    def _apply_actions(self, actions):
        for a in actions or []:
            t = a["type"]
            if t == "remove_all":
                self.cart.clear()
            elif t == "remove_last" and self.cart:
                self.cart.pop()
            elif t == "remove_item":
                for l in self._lines(a["menu"], a.get("temperature")):
                    self.cart.remove(l)
            elif t == "set_quantity":
                f = self._lines(a["menu"], a.get("temperature"))
                if f:
                    f[-1]["qty"] = a["quantity"]
            elif t == "set_temperature":
                f = self._lines(a["menu"])
                if f:
                    f[-1]["temp"] = a["temperature"]
            elif t == "set_temperature_all":
                for i in self.cart:
                    if i["menu"] in a["menus"]:
                        i["temp"] = a["temperature"]
            elif t == "set_temperature_part":
                f = self._lines(a["menu"])
                if f:
                    line = f[-1]
                    n = min(a["count"], line["qty"])
                    if n >= line["qty"]:
                        line["temp"] = a["temperature"]
                    else:
                        line["qty"] -= n
                        self._add(line["menu"], a["temperature"], n, [dict(o) for o in line["options"]], line.get("packaging", False))
            elif t == "remove_line":
                for idx in sorted(a["indexes"], reverse=True):
                    if 0 <= idx < len(self.cart):
                        self.cart.pop(idx)
            elif t == "set_options":
                if 0 <= a["index"] < len(self.cart):
                    line = self.cart[a["index"]]
                    if a["count"] >= line["qty"]:
                        line["options"] = a["options"]
                    else:
                        line["qty"] -= a["count"]
                        self._add(line["menu"], line["temp"], a["count"], a["options"], line.get("packaging", False))
            elif t == "replace_item":
                f = self._lines(a["menu"])
                if f:
                    l = f[-1]
                    self.cart.remove(l)
                    self._add(a["to_menu"], l["temp"], l["qty"], l["options"], l.get("packaging", False))

    def say(self, text: str) -> dict:
        req = main.QueryRequest(query=text, cart_items=self.cart_items(), dialog=self.dialog)
        res = asyncio.run(main._handle_ask(req))
        self.dialog = res.get("dialog")
        if res.get("memo"):
            self.memo = f"{self.memo} / {res['memo']}" if self.memo else res["memo"]
        intent = res.get("intent")
        if intent in ("cancel", "modify"):
            self._apply_actions(res.get("cart_actions"))
        if intent in ("order", "order_and_pay", "dialog"):
            for o in res.get("orders") or []:
                if not o.get("menu"):
                    continue
                opts = ([{"name": d["name"], "count": d["count"]} for d in o["option_details"]]
                        if o.get("option_details") else [{"name": n, "count": 1} for n in o.get("options", [])])
                self._add(o["menu"], o.get("temperature", "ICE"), o.get("quantity", 1), opts, o.get("packaging") is True)
        if intent == "payment" and self.cart:
            self.paid = True
        if intent == "order_and_pay" or res.get("go_payment"):
            self.paid = True
        self.log.append((text, res.get("answer", "")))
        return res

    def cart_view(self):
        return [(i["menu"], i["temp"], i["qty"], tuple(sorted(
            (o["name"] + (f"×{o['count']}" if o["count"] > 1 else "")) for o in i["options"]))) for i in self.cart]


# (제목, 발화 목록, 기대 장바구니, 결제 이동 기대, 비고)
from eval.sim_scenarios import SCENARIOS as ELDER_SCENARIOS  # noqa: E402
from eval.sim_scenarios_cafe import CAFE_SCENARIOS  # noqa: E402

# --cafe: 카페 손님 유형별 시나리오만
SCENARIOS = CAFE_SCENARIOS if "--cafe" in sys.argv else ELDER_SCENARIOS + CAFE_SCENARIOS

_orig_get_menus = admin_db.get_menus


def _with_sold_out(title):
    """제목이 '[품절:메뉴]' 로 시작하면 그 메뉴를 품절로 둔다."""
    import re
    m = re.match(r"\[품절:([^\]]+)\]", title)
    names = {m.group(1)} if m else set()

    def patched():
        out = []
        for x in _orig_get_menus():
            x = dict(x)
            if x["name"] in names:
                x["sold_out"] = True
            out.append(x)
        return out
    admin_db.get_menus = patched


def run():
    bad = 0
    skipped = 0
    for title, utterances, want_cart, want_pay, *rest in SCENARIOS:
        if title.startswith("[LLM]") and not USE_LLM:  # LLM이 있어야 판단되는 시나리오
            skipped += 1
            continue
        _with_sold_out(title)
        k = Kiosk()
        for u in utterances:
            k.say(u)
        got = k.cart_view()
        problems = []
        if want_cart is not None and got != want_cart:
            problems.append(f"장바구니 {got} (기대 {want_cart})")
        if want_pay is not None and k.paid != want_pay:
            problems.append(f"결제이동 {k.paid} (기대 {want_pay})")
        if rest and rest[0] and rest[0] not in k.memo:
            problems.append(f"요청사항 메모 '{k.memo}' (기대 '{rest[0]}' 포함)")
        if problems:
            bad += 1
        if problems or VERBOSE:
            print(f"\n{'✗' if problems else '✓'} {title}")
            for u, a in k.log:
                print(f"   🧓 {u}\n   🤖 {a}")
            for p in problems:
                print(f"   ⚠ {p}")
    n = len(SCENARIOS) - skipped
    print(f"\n시나리오 {n - bad}/{n} 통과" + (f" (LLM 필요 {skipped}건은 건너뜀, --llm 으로 실행)" if skipped else ""))
    return bad


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
