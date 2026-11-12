import json
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_LOG_PATH = os.path.join(DATA_DIR, "intent_logs.jsonl")
INTERACTION_LOG = os.path.join(DATA_DIR, "interaction_logs.jsonl")
FEEDBACK_LOG = os.path.join(DATA_DIR, "feedback_logs.jsonl")

_FALLBACK_MARKERS = ("다시 한 번 말씀", "다시 말씀해", "찾지 못", "알 수 없", "어떤 메뉴를 주문하시겠어요", "오류가 발생")


def _append(path: str, record: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("로그 저장 실패:", e)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_intent_query(text: str, predicted_intent: str) -> None:
    _append(_LOG_PATH, {"text": text, "intent": predicted_intent, "logged_at": _now(), "verified": False})


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


def log_interaction(raw: str, cart_items: list[str], result: dict) -> None:
    _append(INTERACTION_LOG, {
        "raw": raw,
        "fixed": result.get("question", raw),
        "intent": result.get("intent"),
        "answer": result.get("answer"),
        "orders": [{"menu": o.get("menu"), "quantity": o.get("quantity"), "temperature": o.get("temperature")}
                   for o in result.get("orders", [])],
        "cart_actions": result.get("cart_actions"),
        "cart_items": cart_items,
        "flags": outcome_flags(raw, result),
        "logged_at": _now(),
    })


def log_feedback(query: str, answer: str, intent: str | None) -> None:
    _append(FEEDBACK_LOG, {"query": query, "answer": answer, "intent": intent, "logged_at": _now()})
