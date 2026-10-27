import json
import sys
from pathlib import Path

from ai.entity import normalize_text
from ai.logging_utils import FEEDBACK_LOG, INTERACTION_LOG

ROOT = Path(__file__).parent
CASES_FILE = ROOT / "cases_logged.json"
REVIEWED_FILE = Path(INTERACTION_LOG).parent / "reviewed.json"
INTENTS = ["order", "order_and_pay", "payment", "recommend", "qa", "coupon", "cancel", "modify"]


def _read_jsonl(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _load(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def build_queue() -> list[dict]:
    reviewed = set(_load(REVIEWED_FILE, []))
    queue: dict[str, dict] = {}

    for fb in _read_jsonl(FEEDBACK_LOG):
        key = normalize_text(fb["query"])
        queue[key] = {"text": fb["query"], "fixed": fb["query"], "intent": fb.get("intent"),
                      "answer": fb.get("answer", ""), "reasons": ["손님이 '잘못 알아들었어요' 누름"]}

    for row in _read_jsonl(INTERACTION_LOG):
        if not row.get("flags"):
            continue
        key = normalize_text(row["raw"])
        item = queue.setdefault(key, {"text": row["raw"], "fixed": row["fixed"], "intent": row.get("intent"),
                                      "answer": row.get("answer", ""), "reasons": []})
        item["reasons"] += [f for f in row["flags"] if f not in item["reasons"]]

    return [v for k, v in queue.items() if k not in reviewed]


def summary() -> None:
    rows = _read_jsonl(INTERACTION_LOG)
    feedback = _read_jsonl(FEEDBACK_LOG)
    print(f"전체 대화 {len(rows)}건, '잘못 알아들었어요' {len(feedback)}건")
    counts: dict[str, int] = {}
    for r in rows:
        for f in r.get("flags", []):
            counts[f] = counts.get(f, 0) + 1
    for f, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {f}: {n}건")
    print(f"검토 대기 {len(build_queue())}건  (검토 시작: uv run python -m eval.review_logs)")


def review() -> None:
    queue = build_queue()
    if not queue:
        print("검토할 항목이 없어요.")
        return
    cases = _load(CASES_FILE, [])
    reviewed = _load(REVIEWED_FILE, [])
    added = 0
    print(f"검토 대기 {len(queue)}건. 번호=정답 의도 / Enter=건너뛰기 / g=지금 결과가 맞음 / x=무시 / q=종료\n")
    for i, itm in enumerate(queue, 1):
        print(f"[{i}/{len(queue)}] 말한 내용: {itm['text']}")
        if itm["fixed"] != itm["text"]:
            print(f"        보정 후: {itm['fixed']}")
        print(f"        판단: {itm['intent']}  이유: {', '.join(itm['reasons'])}")
        print(f"        답변: {itm['answer'][:120]}")
        print("        " + "  ".join(f"{n}={name}" for n, name in enumerate(INTENTS, 1)))
        try:
            ans = input("        > ").strip().lower()
        except EOFError:
            break
        key = normalize_text(itm["text"])
        if ans == "q":
            break
        if ans == "":
            continue
        if ans == "x":
            reviewed.append(key)
            continue
        label = itm["intent"] if ans == "g" else (INTENTS[int(ans) - 1] if ans.isdigit() and 1 <= int(ans) <= len(INTENTS) else None)
        if not label:
            print("        (알 수 없는 입력이라 건너뛰었어요)")
            continue
        cases.append({"text": itm["text"], "intent": label})
        reviewed.append(key)
        added += 1
    CASES_FILE.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    REVIEWED_FILE.parent.mkdir(exist_ok=True)
    REVIEWED_FILE.write_text(json.dumps(reviewed, ensure_ascii=False), encoding="utf-8")
    print(f"\n정답 케이스 {added}건을 eval/cases_logged.json에 추가했어요. "
          "uv run python -m eval.run_eval --intent 로 다시 점수를 확인하세요.")


if __name__ == "__main__":
    if "--summary" in sys.argv:
        summary()
    else:
        review()
