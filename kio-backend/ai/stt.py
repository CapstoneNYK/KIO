import os
from functools import lru_cache

from faster_whisper import WhisperModel

from ai.dictionary import MENU_KEYWORDS

MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "0"))
BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))

_EXTRA_VOCAB = [
    "카드결제", "카카오페이", "네이버페이", "앱카드", "모바일상품권", "기프트카드",
    "KT VIP", "T멤버십", "CJ ONE", "T우주", "우주패스", "쿠폰",
]

_STYLE_EXAMPLES = [
    "아메리카노 한 잔 줘",
    "카페라떼 두 잔 주세요",
    "바닐라라떼 하나 담아줘",
    "이거 주문할게요",
    "그 중에 1번으로 두 잔 줘",
    "2번 메뉴로 담아줘",
]


def _build_vocabulary_prompt() -> str:
    menus = sorted(set(MENU_KEYWORDS.values()))
    vocab_line = ", ".join(menus + _EXTRA_VOCAB)
    style_line = " ".join(_STYLE_EXAMPLES)
    return f"{vocab_line}. {style_line}"

_VOCAB_PROMPT = _build_vocabulary_prompt()


@lru_cache(maxsize=1)
def _load_model() -> WhisperModel:
    return WhisperModel(
        MODEL_SIZE,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        cpu_threads=CPU_THREADS,
    )


def transcribe(audio_path: str, language: str = "ko") -> str:
    model = _load_model()
    segments, _info = model.transcribe(
        audio_path,
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=BEAM_SIZE,
        initial_prompt=_VOCAB_PROMPT,
    )
    text = "".join(segment.text for segment in segments)
    return text.strip()
