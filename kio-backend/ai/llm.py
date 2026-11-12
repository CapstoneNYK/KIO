import os

from langchain_ollama import ChatOllama

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
OLLAMA_INTENT_MODEL = os.getenv("OLLAMA_INTENT_MODEL", OLLAMA_MODEL)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")


def get_llm(temperature: float = 0.0, model: str | None = None, num_predict: int | None = None) -> ChatOllama:
    return ChatOllama(
        model=model or OLLAMA_MODEL,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
        keep_alive=OLLAMA_KEEP_ALIVE,
        num_predict=num_predict,
    )
