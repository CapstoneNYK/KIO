import json
import os
from datetime import datetime, timezone

_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "intent_logs.jsonl"
)


def log_intent_query(text: str, predicted_intent: str) -> None:
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        record = {
            "text": text,
            "intent": predicted_intent,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "verified": False,
        }
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("intent 로그 저장 실패:", e)
