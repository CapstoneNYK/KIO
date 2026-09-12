"""자체 호스팅 LLM 클라이언트.

기존에는 intent.py, recommend.py에서 각각 OpenAI(gpt-4o) 유료 API를 직접
호출했다. 교수님 피드백(유료 LLM API 사용 지양, 자체 AI 구축)에 따라
로컬에서 Ollama로 띄운 오픈소스 LLM을 사용하도록 교체한다.

사전 준비 (PC 1회 설정):
  1) https://ollama.com 에서 Ollama 설치
  2) 터미널에서 `ollama pull qwen2.5:7b-instruct` 실행 (최초 1회, 모델 다운로드)
     - 사양이 낮으면 .env의 OLLAMA_MODEL을 `qwen2.5:3b-instruct` 등 더 가벼운
       모델로 바꿔서 사용
  3) Ollama는 설치 후 백그라운드에서 상시 구동되며 기본적으로
     http://localhost:11434 에서 API 서버 역할을 한다 (별도 실행 불필요)

의도 분류(6지선다, 단순 작업)는 매 요청마다 호출되는데 추천/QA와 같은 무거운
모델을 쓰면 전체 응답이 느려진다. OLLAMA_INTENT_MODEL을 따로 지정하면 의도
분류만 더 가벼운 모델로 처리해서 체감 속도를 개선할 수 있다 (미설정 시
OLLAMA_MODEL과 동일한 모델 사용).

이후 실제 서비스 품질을 더 올리고 싶다면, 오늘 도입한 이 모델을 베이스로
주문 대화 로그를 모아 파인튜닝하는 것을 다음 단계로 진행하면 된다.
"""

import os

from langchain_ollama import ChatOllama

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
# 의도 분류 전용 모델. 미설정 시 OLLAMA_MODEL을 그대로 사용.
OLLAMA_INTENT_MODEL = os.getenv("OLLAMA_INTENT_MODEL", OLLAMA_MODEL)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def get_llm(temperature: float = 0.0, model: str | None = None) -> ChatOllama:
    """설정된 Ollama 모델을 사용하는 ChatOllama 인스턴스를 반환한다.

    LangChain의 ChatOpenAI와 동일한 방식(LCEL 체인, 프롬프트 템플릿과 결합)으로
    쓸 수 있어 기존 intent.py / recommend.py의 체인 구성은 거의 그대로 재사용한다.
    model을 지정하지 않으면 기본 OLLAMA_MODEL을 사용한다.
    """
    return ChatOllama(
        model=model or OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
    )
