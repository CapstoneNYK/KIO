# [llm.py] Ollama(로컬 LLM) 연결 설정과 LLM 객체 생성/워밍업.
import os

from langchain_ollama import ChatOllama

# 모델 이름·주소 등 설정(환경변수). 의도 분류용 모델(OLLAMA_INTENT_MODEL)은 따로 지정하지 않으면 응답용과 같은 모델
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_INTENT_MODEL = os.getenv("OLLAMA_INTENT_MODEL", OLLAMA_MODEL)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")


# LLM 객체 생성. temperature(무작위성), model(기본: 응답용), num_predict(최대 토큰 수)
def get_llm(temperature: float = 0.0, model: str | None = None, num_predict: int | None = None) -> ChatOllama:
    return ChatOllama(
        model=model or OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
        keep_alive=OLLAMA_KEEP_ALIVE,
        num_predict=num_predict,
    )


# 서버 시작 시 모델을 미리 메모리에 올린다. Ollama 가 꺼져 있어도 서버는 계속 뜬다(실패는 출력만)
def warmup() -> None:
    """Ollama 모델(의도 분류용·응답용)을 미리 메모리에 올린다. Ollama가 꺼져 있어도 서버는 계속 뜬다."""
    for model in {OLLAMA_MODEL, OLLAMA_INTENT_MODEL}:
        try:
            get_llm(model=model, num_predict=1).invoke("안녕")
        except Exception as e:
            print(f"[warmup] LLM '{model}' 워밍업 실패:", e)
