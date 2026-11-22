"""음성인식(STT) 보정 후보 리포트 + 보정표 추가 도구.

    python -m tools.stt_report                  # 최근 로그에서 보정 후보 보기
    python -m tools.stt_report --days 14        # 기간 지정(기본 30일)
    python -m tools.stt_report --list           # 지금 등록된 사용자 보정표
    python -m tools.stt_report --add "셔츠 갈아=샷 추가해"   # 보정 추가(data/stt_fixes.json)
    python -m tools.stt_report --remove "셔츠 갈아"

리포트는 두 가지를 보여 준다.
  1) 이미 고쳐진 말(원문 → 보정): 보정이 잘 동작하는지, 같은 오류가 얼마나 자주 나오는지
  2) 못 알아들은 말(원문 그대로 fallback): 음성인식이 엉뚱하게 들었을 가능성이 있는 말 — 사람이 보고 --add 로 추가
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from ai.entity import fix_stt_errors
from ai.logging_utils import INTERACTION_LOG
from ai.stt_fixes import FIXES_PATH, MIN_WRONG_LEN


def _read_logs(days: int) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []
    try:
        with open(INTERACTION_LOG, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if datetime.fromisoformat(r["logged_at"]) >= since:
                        rows.append(r)
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return rows


def _load_fixes() -> dict:
    try:
        with open(FIXES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_fixes(fixes: dict) -> None:
    os.makedirs(os.path.dirname(FIXES_PATH), exist_ok=True)
    with open(FIXES_PATH, "w", encoding="utf-8") as f:
        json.dump(fixes, f, ensure_ascii=False, indent=2)


def report(days: int, top: int) -> None:
    rows = _read_logs(days)
    print(f"최근 {days}일 대화 {len(rows)}건\n")

    fixed = Counter((r["raw"].strip(), r["fixed"].strip()) for r in rows if "stt_fixed" in (r.get("flags") or []))
    print("[1] 이미 보정된 말 (원문 → 보정)")
    for (raw, fx), n in fixed.most_common(top) or []:
        print(f"  {n:>3}회  {raw}  →  {fx}")
    if not fixed:
        print("  (없음)")

    miss = Counter()
    ctx: dict = {}
    for r in rows:
        raw = (r.get("raw") or "").strip()
        if "fallback" in (r.get("flags") or []) and "stt_fixed" not in (r.get("flags") or []) and raw:
            miss[raw] += 1
            ctx[raw] = (r.get("answer") or "")[:40]
    print("\n[2] 못 알아들은 말 — 음성인식 오류 후보 (보정하려면 --add \"틀린말=올바른말\")")
    for raw, n in miss.most_common(top):
        print(f"  {n:>3}회  {raw}    (답변: {ctx[raw]})")
    if not miss:
        print("  (없음)")


def add(spec: str) -> int:
    if "=" not in spec:
        print('형식: --add "틀린말=올바른말"')
        return 1
    wrong, right = (x.strip() for x in spec.split("=", 1))
    if len(wrong.replace(" ", "")) < MIN_WRONG_LEN or not right:
        print(f"틀린말은 {MIN_WRONG_LEN}글자 이상, 올바른 말은 비우지 말아 주세요. (한 글자 교정은 멀쩡한 말까지 바꿔요)")
        return 1
    fixes = _load_fixes()
    fixes[wrong] = right
    _save_fixes(fixes)
    print(f'추가했어요: "{wrong}" → "{right}"  (서버를 다시 켜지 않아도 적용돼요)')
    print("  확인:", fix_stt_errors(wrong))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="STT 보정 후보 리포트 / 보정표 관리")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--add", metavar="틀린말=올바른말")
    ap.add_argument("--remove", metavar="틀린말")
    a = ap.parse_args()
    if a.add:
        return add(a.add)
    if a.remove:
        fixes = _load_fixes()
        if fixes.pop(a.remove, None) is None:
            print("없는 항목이에요.")
            return 1
        _save_fixes(fixes)
        print("지웠어요.")
        return 0
    if a.list:
        for w, r in _load_fixes().items():
            print(f"  {w}  →  {r}")
        return 0
    report(a.days, a.top)
    return 0


if __name__ == "__main__":
    sys.exit(main())
