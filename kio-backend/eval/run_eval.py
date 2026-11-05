import json
import sys
from pathlib import Path

from ai.cart_command import detect_cart_command
from ai.entity import extract_multi_order, fix_stt_errors
from ai.order import entities_to_orders, validate_options
from ai.preference import recommend_by_conditions
from app.admin import db as admin_db
from eval.cases import CART_CASES, ORDER_CASES, RECO_CASES

import re


def eval_order(menus):
    names = [m["name"] for m in menus]
    fails, ok = [], 0
    for text, expected in ORDER_CASES:
        orders = entities_to_orders(extract_multi_order(text, names))
        orders = [o for o in orders if o["menu"]]
        orders, _ = validate_options(orders, menus)
        problems = []
        if len(orders) != len(expected):
            problems.append(f"주문 개수 {len(orders)} (기대 {len(expected)})")
        else:
            for got, exp in zip(orders, expected):
                if got["menu"] != exp["menu"]:
                    problems.append(f"메뉴 {got['menu']} (기대 {exp['menu']})")
                    continue
                if got["temperature"] != exp["temp"]:
                    problems.append(f"{exp['menu']} 온도 {got['temperature']} (기대 {exp['temp']})")
                if got["quantity"] != exp["qty"]:
                    problems.append(f"{exp['menu']} 수량 {got['quantity']} (기대 {exp['qty']})")
                if "opts" in exp:
                    have = {d["kind"]: (d["name"], d["count"]) for d in got["option_details"] if d["kind"] != "other"}
                    want = {k: (v if isinstance(v, tuple) else (v, 1)) for k, v in exp["opts"].items()}
                    if have != want:
                        problems.append(f"옵션 {have} (기대 {want})")
                if "pack" in exp and got["packaging"] != exp["pack"]:
                    problems.append(f"포장 {got['packaging']} (기대 {exp['pack']})")
        if problems:
            fails.append({"text": text, "problems": problems})
        else:
            ok += 1
    return ok, len(ORDER_CASES), fails


def eval_cart(menus):
    fails, ok = [], 0
    from ai.cart_command import clear_pending
    for text, cart, exp in CART_CASES:
        clear_pending()
        got = detect_cart_command(fix_stt_errors(text), cart, menus)
        problems = []
        if exp is None:
            if got is not None:
                problems.append(f"명령으로 오탐: {got['intent']} {got['cart_actions']}")
        elif got is None:
            problems.append("명령을 인식하지 못함")
        else:
            if got["intent"] != exp["intent"]:
                problems.append(f"intent {got['intent']} (기대 {exp['intent']})")
            acts = got["cart_actions"]
            if len(acts) != len(exp["actions"]):
                problems.append(f"액션 {acts} (기대 {exp['actions']})")
            else:
                for a, e in zip(acts, exp["actions"]):
                    if any(a.get(k) != v for k, v in e.items()):
                        problems.append(f"액션 {a} (기대 {e})")
        if problems:
            fails.append({"text": text, "problems": problems})
        else:
            ok += 1
    return ok, len(CART_CASES), fails


def eval_reco(menus):
    by_name = {m["name"]: m for m in menus}
    fails, ok = [], 0
    for text, cond in RECO_CASES:
        rec = recommend_by_conditions(text, menus)
        problems = []
        if cond is None:
            if rec is not None:
                problems.append("조건이 없는데 규칙 추천이 개입함")
        elif rec is None:
            problems.append("조건을 인식하지 못함")
        else:
            if not rec.menus:
                problems.append("추천 결과 없음")
            if "limit" in cond and len(rec.menus) > cond["limit"]:
                problems.append(f"개수 {len(rec.menus)} (최대 {cond['limit']})")
            for raw in rec.menus:
                name = re.sub(r"^(핫|아이스) ", "", raw)
                m = by_name.get(name)
                if m is None:
                    problems.append(f"없는 메뉴 {raw}")
                    continue
                if cond.get("coffee_only") and m["category"] not in ("커피", "디카페인"):
                    problems.append(f"{name}: 커피가 아님 ({m['category']})")
                if cond.get("caffeine") is False and m["caffeine"]:
                    problems.append(f"{name}: 카페인 있음")
                if cond.get("caffeine") is True and not m["caffeine"]:
                    problems.append(f"{name}: 카페인 없음")
                if "temp" in cond and cond["temp"] not in m["temps"]:
                    problems.append(f"{name}: {cond['temp']} 불가")
                if any(t not in m["tags"] for t in cond.get("tags", [])) and not rec.relaxed:
                    problems.append(f"{name}: 태그 {cond['tags']} 없음 {m['tags']}")
                if any(t in m["tags"] for t in cond.get("exclude_tags", [])):
                    problems.append(f"{name}: 제외 태그 포함 {m['tags']}")
                if "max_price" in cond and m["price"] > cond["max_price"] and not rec.relaxed:
                    problems.append(f"{name}: {m['price']}원 > {cond['max_price']}")
                if m["category"] in cond.get("cats_not", []):
                    problems.append(f"{name}: 제외 카테고리 {m['category']}")
                if "cats_only" in cond and m["category"] not in cond["cats_only"]:
                    problems.append(f"{name}: 카테고리 {m['category']}")
        if cond and "min_categories" in cond:
            fam = {"디카페인": "커피"}
            kinds = {fam.get(by_name[n.removeprefix("핫 ").removeprefix("아이스 ")]["category"],
                             by_name[n.removeprefix("핫 ").removeprefix("아이스 ")]["category"])
                     for n in rec.menus if n.removeprefix("핫 ").removeprefix("아이스 ") in by_name}
            if len(kinds) < cond["min_categories"]:
                problems.append(f"종류가 다양하지 않음 {sorted(kinds)}")
        if problems:
            fails.append({"text": text, "problems": problems})
        else:
            ok += 1
    return ok, len(RECO_CASES), fails


def run_set(title, menus, order, cart, reco, report):
    global ORDER_CASES, CART_CASES, RECO_CASES
    ORDER_CASES, CART_CASES, RECO_CASES = order, cart, reco
    total_ok = total = 0
    for name, fn in (("주문 추출·옵션", eval_order), ("장바구니 취소·변경", eval_cart), ("조건 추천", eval_reco)):
        ok, n, fails = fn(menus)
        total_ok += ok
        total += n
        report[f"{title} / {name}"] = {"correct": ok, "total": n, "accuracy": round(ok / n * 100, 1), "failures": fails}
        print(f"\n=== [{title}] {name}: {ok}/{n} ({ok / n * 100:.1f}%)")
        for f in fails:
            print(f"  ✗ {f['text']}")
            for p in f["problems"]:
                print(f"      - {p}")
    return total_ok, total


def eval_dialog(menus):
    from ai.cart_command import clear_pending
    from eval.cases_extra import DIALOG_CASES
    fails, ok = [], 0
    for title, turns in DIALOG_CASES:
        clear_pending()
        problems = []
        for text, cart, exp in turns:
            got = detect_cart_command(fix_stt_errors(text), cart, menus)
            if exp is None:
                if got is not None:
                    problems.append(f"'{text}' 명령으로 오탐: {got['cart_actions']}")
            elif got is None:
                problems.append(f"'{text}' 인식 못함")
            else:
                if got["intent"] != exp["intent"]:
                    problems.append(f"'{text}' intent {got['intent']} (기대 {exp['intent']})")
                acts = got["cart_actions"]
                if len(acts) != len(exp["actions"]):
                    problems.append(f"'{text}' 액션 {acts} (기대 {exp['actions']})")
                else:
                    for a, e in zip(acts, exp["actions"]):
                        if any(a.get(k) != v for k, v in e.items()):
                            problems.append(f"'{text}' 액션 {a} (기대 {e})")
        if problems:
            fails.append({"text": title, "problems": problems})
        else:
            ok += 1
    clear_pending()
    n = len(DIALOG_CASES)
    print(f"\n=== [대화형] 되묻기 이어 받기: {ok}/{n} ({ok / n * 100:.1f}%)")
    for f in fails:
        print(f"  ✗ {f['text']}")
        for p in f["problems"]:
            print(f"      - {p}")
    return ok, n, fails


def eval_slots(menus):
    """슬롯 채우기 대화: 질문 순서와 최종 주문이 정답과 같은지."""
    from ai.cart_command import detect_cart_command as _detect
    from ai.dialog import answer_slot, start_dialog
    from eval.cases_dialog import DIALOG_SLOT_CASES, PASS
    names = [m["name"] for m in menus]
    fails, ok = [], 0

    def pending_of(res):
        st = res["state"]
        return st["queue"][0]["pending"] if st else None

    for title, first, answers, want_seq, want_orders in DIALOG_SLOT_CASES:
        orders = entities_to_orders(extract_multi_order(fix_stt_errors(first), names))
        orders, _ = validate_options([o for o in orders if o["menu"]], menus)
        problems, seq, done = [], [], []
        res = start_dialog(orders, menus)
        if res is None:
            if want_seq:
                problems.append("되묻기가 시작되지 않음")
        elif not want_seq:
            problems.append(f"물어볼 게 없는데 되묻기가 시작됨: {res['answer']}")
        else:
            seq.append(pending_of(res))
            done += res["orders"]
            for a in answers:
                if res["state"] is None:
                    break
                nxt = answer_slot(res["state"], fix_stt_errors(a), menus, [], _detect)
                if nxt is None:
                    seq.append(PASS)
                    break
                res = nxt
                seq.append(pending_of(res))
                done += res["orders"]
        if seq != want_seq:
            problems.append(f"질문 순서 {seq} (기대 {want_seq})")
        got = [(o["menu"], o["temperature"], o["quantity"],
                {d["name"] + (f" ×{d['count']}" if d["count"] > 1 else "") for d in o["option_details"]}) for o in done]
        if got != want_orders:
            problems.append(f"최종 주문 {got} (기대 {want_orders})")
        if problems:
            fails.append({"text": title, "problems": problems})
        else:
            ok += 1
    n = len(DIALOG_SLOT_CASES)
    print(f"\n=== [대화형] 옵션 되묻기(슬롯 채우기): {ok}/{n} ({ok / n * 100:.1f}%)")
    for f in fails:
        print(f"  ✗ {f['text']}")
        for p in f["problems"]:
            print(f"      - {p}")
    return ok, n, fails


def eval_intent_fast(menus):
    from ai.fast_intent import fast_classify
    from eval.cases_intent import INTENT_CASES
    names = [m["name"] for m in menus]
    decided = right = 0
    wrong = []
    from ai.entity import fix_stt_errors
    for text, expected in INTENT_CASES:
        got = fast_classify(fix_stt_errors(text), names)
        if got is None:
            continue
        decided += 1
        if got == expected:
            right += 1
        else:
            wrong.append({"text": text, "problems": [f"규칙 예측 {got} (정답 {expected})"]})
    n = len(INTENT_CASES)
    print(f"\n=== [규칙] 빠른 의도 분류: 규칙이 결정 {decided}/{n} ({decided / n * 100:.1f}%), 그중 정답 {right}/{decided or 1}, 오분류 {len(wrong)}건")
    for f in wrong:
        print(f"  ✗ {f['text']}  {f['problems'][0]}")
    return {"decided": decided, "total": n, "right": right, "wrong": wrong}


def eval_cart_route(menus):
    """장바구니 명령(수정·취소)로 라벨된 로그 케이스: 실제 경로(STT 보정 → detect_cart_command)로 검증."""
    from ai.cart_command import clear_pending
    from eval.cases_intent import CART_ROUTE_CASES
    sample_cart = ["아이스 아메리카노 ×2", "따뜻한 카페라떼 ×2"]
    ok, fails = 0, []
    for text, expected in CART_ROUTE_CASES:
        clear_pending()
        got = detect_cart_command(fix_stt_errors(text), sample_cart, menus)
        if got is not None and got["intent"] == expected:
            ok += 1
        else:
            fails.append({"text": text, "problems": [f"예측 {got['intent'] if got else None} (정답 {expected})"]})
    n = len(CART_ROUTE_CASES)
    print(f"\n=== 장바구니 명령 경로 (로그 케이스): {ok}/{n}")
    for f in fails:
        print(f"  ✗ {f['text']}  {f['problems'][0]}")
    return {"correct": ok, "total": n, "accuracy": round(ok / n * 100, 1) if n else 100.0, "failures": fails}


def eval_intent(report, menus):
    from ai.fast_intent import fast_classify
    from ai.intent import classify_intent
    from eval.cases_intent import INTENT_CASES
    names = [m["name"] for m in menus]
    llm_ok = pipe_ok = 0
    llm_fails, pipe_fails = [], []
    confusion = {}
    per_class = {}
    from ai.entity import fix_stt_errors
    for text, expected in INTENT_CASES:
        text = fix_stt_errors(text)
        llm = classify_intent(text)
        fast = fast_classify(text, names)
        pipe = fast or llm
        c = per_class.setdefault(expected, {"n": 0, "llm": 0, "pipeline": 0})
        c["n"] += 1
        if llm == expected:
            llm_ok += 1
            c["llm"] += 1
        else:
            llm_fails.append({"text": text, "problems": [f"예측 {llm} (정답 {expected})"]})
        if pipe == expected:
            pipe_ok += 1
            c["pipeline"] += 1
        else:
            key = f"{expected}->{pipe}"
            confusion[key] = confusion.get(key, 0) + 1
            pipe_fails.append({"text": text, "problems": [f"예측 {pipe} (정답 {expected}) [{'규칙' if fast else 'LLM'}]"]})
    n = len(INTENT_CASES)
    print(f"\n=== [LLM 단독] 의도 분류: {llm_ok}/{n} ({llm_ok / n * 100:.1f}%)")
    for f in llm_fails:
        print(f"  ✗ {f['text']}  {f['problems'][0]}")
    print(f"\n=== [실제 파이프라인: 규칙 → LLM] 의도 분류: {pipe_ok}/{n} ({pipe_ok / n * 100:.1f}%)")
    for f in pipe_fails:
        print(f"  ✗ {f['text']}  {f['problems'][0]}")
    print("\n클래스별 정확도 (LLM 단독 / 파이프라인)")
    for k, c in per_class.items():
        print(f"  {k:14s} {c['llm']}/{c['n']}  /  {c['pipeline']}/{c['n']}")
    report["LLM / 의도 분류(LLM 단독)"] = {"correct": llm_ok, "total": n, "accuracy": round(llm_ok / n * 100, 1), "failures": llm_fails}
    report["LLM / 의도 분류(파이프라인)"] = {"correct": pipe_ok, "total": n, "accuracy": round(pipe_ok / n * 100, 1),
                                      "confusion": confusion, "per_class": per_class, "failures": pipe_fails}


def main():
    from eval import cases, cases_hard, cases_extra
    if "--live" not in sys.argv:
        import tempfile
        admin_db.DB_PATH = Path(tempfile.mkdtemp()) / "eval.db"
    admin_db.init_db()
    menus = admin_db.get_menus()
    report = {}
    sets = [
        ("기본셋", cases.ORDER_CASES, cases.CART_CASES, cases.RECO_CASES),
        ("자연발화셋", cases_hard.ORDER_CASES, cases_hard.CART_CASES, cases_hard.RECO_CASES),
        ("추가셋", cases_extra.ORDER_CASES, cases_extra.CART_CASES, cases_extra.RECO_CASES),
    ]
    all_ok = all_n = 0
    for title, o, c, r in sets:
        ok, n = run_set(title, menus, o, c, r, report)
        all_ok += ok
        all_n += n
    print(f"\n전체(규칙 기반): {all_ok}/{all_n} ({all_ok / all_n * 100:.1f}%)")
    report["overall_rules"] = {"correct": all_ok, "total": all_n, "accuracy": round(all_ok / all_n * 100, 1)}
    d_ok, d_n, d_fails = eval_dialog(menus)
    report["대화형 / 되묻기 이어 받기"] = {"correct": d_ok, "total": d_n, "accuracy": round(d_ok / d_n * 100, 1), "failures": d_fails}
    s_ok, s_n, s_fails = eval_slots(menus)
    report["대화형 / 옵션 되묻기(슬롯 채우기)"] = {"correct": s_ok, "total": s_n, "accuracy": round(s_ok / s_n * 100, 1), "failures": s_fails}
    report["intent_rules"] = eval_intent_fast(menus)
    report["장바구니 명령 경로 (로그 케이스)"] = eval_cart_route(menus)
    if "--intent" in sys.argv:
        eval_intent(report, menus)
    out = Path(__file__).parent / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"리포트 저장: {out}")

if __name__ == "__main__":
    main()
