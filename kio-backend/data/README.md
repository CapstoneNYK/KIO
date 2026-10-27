# 의도 분류 파인튜닝용 데이터

## 파일 구성

- `intent_seed.jsonl`: 처음 파인튜닝을 시작해볼 수 있도록 자동 생성한 예시 문장 데이터 (git에 커밋됨).
  `generate_intent_seed.py`를 다시 실행하면 재생성됨.
- `intent_logs.jsonl`: 서비스를 실제로 쓰는 동안 `/api/ask` 호출마다 자동으로 쌓이는 로그
  (git에는 커밋 안 됨 — `.gitignore` 처리). 각 줄은 `{text, intent, logged_at, verified}` 형식이고,
  `intent`는 **모델이 예측한 값**이지 사람이 확인한 정답이 아니다.

## 데이터를 계속 쌓아가는 흐름

1. 지금은 `intent_seed.jsonl`만으로 파인튜닝 실험을 시작할 수 있음
2. 팀원들이 계속 테스트하면서 `intent_logs.jsonl`에 실제 대화가 쌓임
3. 파인튜닝하기 전에 `intent_logs.jsonl`을 열어서 잘못 분류된 줄의 `intent` 값을 사람이 직접 고치고
   `verified: true`로 표시 (전부 다 검토하기 부담되면 `verified: false`인 것 위주로 우선 검토)
4. 검토가 끝난 로그를 `intent_seed.jsonl`과 합쳐서 최종 학습 데이터셋을 만듦
   (간단하게는 `cat intent_seed.jsonl intent_logs.jsonl > train.jsonl`처럼 합치면 됨)
5. 사용량이 늘어날수록 3~4번을 반복하면서 데이터셋이 계속 커짐 → 다음 파인튜닝 때 반영

이 방식으로 "처음엔 합성 데이터로 시작 → 실제 사용 데이터로 점점 보강"하는 게 가능하다.
