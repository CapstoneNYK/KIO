"""의도 분류 파인튜닝용 학습 데이터 축적 로거.

지금 당장 파인튜닝을 안 하더라도, 실제 사용자가 어떤 문장을 말했고 모델이
그걸 어떤 의도로 분류했는지 기록해두면 나중에 파인튜닝 데이터로 바로 활용할
수 있다. data/intent_seed.jsonl(자동 생성한 초기 데이터)과 이 파일이 쌓아주는
data/intent_logs.jsonl(실사용 데이터)을 나중에 합쳐서 학습 데이터셋을 키워가는
방식이다.

주의: 여기 기록되는 intent는 "정답"이 아니라 모델의 예측값이다. 파인튜닝에
쓰기 전에는 반드시 사람이 한 번 검토해서 잘못 분류된 줄을 고쳐야 한다.
"""

import json
import os
from datetime import datetime, timezone

_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "intent_logs.jsonl"
)


def log_intent_query(text: str, predicted_intent: str) -> None:
    """실제 사용자 발화와 예측된 의도를 JSONL 한 줄로 추가한다.

    로깅이 실패해도 실제 서비스 흐름(주문/추천/QA 응답)을 막으면 안 되므로
    예외는 삼키고 콘솔에만 출력한다.
    """
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        record = {
            "text": text,
            "intent": predicted_intent,
            "logged_at": datetime.now(timezone.utc).isoformat(),
            "verified": False,  # 사람이 검토해서 라벨을 확인/수정하면 true로 바꿔서 관리
        }
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print("intent 로그 저장 실패:", e)
