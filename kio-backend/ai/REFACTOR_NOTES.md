# ai_commented 리팩토링 정리 (원본 ai/ 는 그대로)

## 새 파일
- korean.py : normalize_text / rx / rx_keep / has_final / 숫자표(NUM_WORDS_4·5·10) / to_int
- vocab.py : 온도 단어 공통(HOT_CORE·ICE_CORE) + 파일별 추가 단어, LEVEL_MORE
- session.py : 세션별 대화 상태(last_recommended / last_asked / pending_temp), 10분 TTL
- data_source.py : recommend/discount 가 DB(app.admin.db)를 가져오는 창구 (set_provider 로 교체 가능)

## 동작이 바뀐 곳 (1단계 이후 의도한 변경)
- fast_intent: '쿠폰 있어요' → coupon
- preference: '안 달/안 쓴…' 부정 태그 오동작 수정
- menu_match: '딸기 쉐이크' → 딸기라떼 (되돌리려면 해당 규칙에서 `딸기\s*쉐이크` 삭제)
- ㅐ 정규화 때문에 안 맞던 표현 수정: '아이스 빼고', '딸기 들어간 거 줄래'(주문으로 인식), '안 해요'(샷 양 되묻기), '하신대/하시래/냉' 등
- cart_command: '찬 거/찬 걸/차게/뜨아' 온도 변경 인식

## main.py 분리 (완료)
- main.py 는 서버 설정 + API 입구(/api/ask, /api/feedback)만 남았다(870줄 → 117줄)
- ai/pipeline.py : 요청 처리 본체(handle_ask). 단계별 _step_* 함수, 위→아래가 우선순위
- ai/followup.py : "1번 주세요/그걸로" 같은 이어 말하기, 방금 추천·질문한 메뉴 기억 (주문 dict 생성은 entity_for 하나로 통합)
- ai/memo.py : 요청사항 메모, ai/quick_answers.py : LLM 없이 답하는 안내(인기·할인·온도·종류·이름 겹침)
- app/voice/router.py : /api/stt, /api/tts
- ai/session.py : 세션별 상태 + set_session/current_state(요청마다 ContextVar)
- QueryRequest.session_id : 프론트가 안 보내면 "" 하나를 공유(예전 동작). 키오스크마다 분리하려면 프론트가 UUID 를 만들어 /api/ask 에 보내면 된다
- eval/sim_elder.py 는 main 대신 ai.pipeline 을 부르도록 바꿨다
