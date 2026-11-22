# [logging_utils.py] 의도 분류·대화·피드백을 JSONL 파일로 쌓는 로깅(나중에 오분류 분석용).
import json
import os
from datetime import datetime, timezone

# 로그 저장 위치: 상위 폴더의 data/ 아래 3개 파일
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_LOG_PATH = os.path.join(DATA_DIR, "intent_logs.jsonl")
INTERACTION_LOG = os.path.join(DATA_DIR, "interaction_logs.jsonl")
FEEDBACK_LOG = os.path.join(DATA_DIR, "feedback_logs.jsonl")

# 답변에 이 문구가 들어 있으면 '제대로 못 알아들음(fallback)'으로 표시
_FALLBACK_MARKERS = ("다시 한 번 말씀", "다시 말씀해", "찾지 못", "알 수 없", "어떤 메뉴를 주문하시겠어요", "오류가 발생", "직원에게 문의")


# JSONL 한 줄 추가(실패해도 서비스에는 영향 없게 예외를 삼킴)
def _append(path: str, record: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("로그 저장 실패:", e)


# UTC 현재 시각 문자열
def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# 의도 분류 결과 로그(verified=False: 나중에 사람이 검수)
def log_intent_query(text: str, predicted_intent: str) -> None:
    _append(_LOG_PATH, {"text": text, "intent": predicted_intent, "logged_at": _now(), "verified": False})


# 결과에 문제 표시 붙이기: stt_fixed(STT 교정됨) / fallback / no_menu / sold_out / stock_limited
def outcome_flags(raw: str, result: dict) -> list[str]:
    flags = []
    if raw != result.get("question", raw):
        flags.append("stt_fixed")
    answer = result.get("answer", "") or ""
    if any(m in answer for m in _FALLBACK_MARKERS):
        flags.append("fallback")
    if result.get("intent") == "order":
        if not any(o.get("menu") for o in result.get("orders", [])):
            flags.append("no_menu")
        if result.get("sold_out"):
            flags.append("sold_out")
        if "재고가" in answer:
            flags.append("stock_limited")
    return flags


# 한 번의 대화(원문·교정문·의도·답변·주문·장바구니·플래그) 기록
def log_interaction(raw: str, cart_items: list[str], result: dict) -> None:
    _append(INTERACTION_LOG, {
        "raw": raw,
        "fixed": result.get("question", raw),
        "intent": result.get("intent"),
        "answer": (result.get("answer") or "").replace("**", "") or None,  # 굵게 표시(**) 는 화면용이라 로그에는 뺀다
        "orders": [{"menu": o.get("menu"), "quantity": o.get("quantity"), "temperature": o.get("temperature")}
                   for o in result.get("orders", [])],
        "cart_actions": result.get("cart_actions"),
        "cart_items": cart_items,
        "flags": outcome_flags(raw, result),
        "logged_at": _now(),
    })


# 사용자 피드백(질문·답변·의도) 기록
def log_feedback(query: str, answer: str, intent: str | None) -> None:
    _append(FEEDBACK_LOG, {"query": query, "answer": (answer or "").replace("**", ""), "intent": intent, "logged_at": _now()})

