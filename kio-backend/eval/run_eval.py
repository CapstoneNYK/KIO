"""규칙 기반 계층 정확도 측정.  실행:  uv run python -m eval.run_eval  (kio-backend 폴더에서)

- LLM/GPU 없이 돌아간다 (주문 추출, 옵션 구조화, 장바구니 명령, 조건 추천).
- 현재 관리자 DB의 메뉴를 기준으로 평가한다 (기본 시드 메뉴 가정).
- 결과는 콘솔과 eval/report.json 에 저장된다.
- 의도 분류(LLM)는 --intent 로 별도 측정 (Ollama 실행 필요).
"""
import json
import sys
from pathlib import Path

from ai.cart_command import detect_cart_command
from ai.entity import extract_multi_order
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
    for text, cart, exp in CART_CASES:
        got = detect_cart_command(text, cart, menus)
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
                # 조건이 완화된 경우(relaxed)는 안내 문구가 있으므로 완화되지 않은 조건만 검사한다
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


def eval_intent(report):
    """의도 분류(LLM) 정확도. Ollama 가 실행 중이어야 한다."""
    from ai.intent import classify_intent
    from eval.cases_intent import INTENT_CASES
    ok, fails = 0, []
    confusion = {}
    for text, expected in INTENT_CASES:
        got = classify_intent(text)
        if got == expected:
            ok += 1
        else:
            fails.append({"text": text, "problems": [f"예측 {got} (정답 {expected})"]})
            confusion[f"{expected}->{got}"] = confusion.get(f"{expected}->{got}", 0) + 1
    n = len(INTENT_CASES)
    print(f"\n=== [LLM] 의도 분류: {ok}/{n} ({ok / n * 100:.1f}%)")
    for f in fails:
        print(f"  ✗ {f['text']}  {f['problems'][0]}")
    report["LLM / 의도 분류"] = {"correct": ok, "total": n, "accuracy": round(ok / n * 100, 1),
                              "confusion": confusion, "failures": fails}


def main():
    from eval import cases, cases_hard
    admin_db.init_db()
    menus = admin_db.get_menus()
    report = {}
    sets = [
        ("기본셋", cases.ORDER_CASES, cases.CART_CASES, cases.RECO_CASES),
        ("자연발화셋", cases_hard.ORDER_CASES, cases_hard.CART_CASES, cases_hard.RECO_CASES),
    ]
    all_ok = all_n = 0
    for title, o, c, r in sets:
        ok, n = run_set(title, menus, o, c, r, report)
        all_ok += ok
        all_n += n
    print(f"\n전체(규칙 기반): {all_ok}/{all_n} ({all_ok / all_n * 100:.1f}%)")
    report["overall_rules"] = {"correct": all_ok, "total": all_n, "accuracy": round(all_ok / all_n * 100, 1)}
    if "--intent" in sys.argv:
        eval_intent(report)
    out = Path(__file__).parent / "report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"리포트 저장: {out}")


if __name__ == "__main__":
    main()
