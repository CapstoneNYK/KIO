import os
import re
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


# Whisper는 조용하거나 잡음뿐인 구간에서 학습 데이터의 자막 문구를 지어내곤 한다("감사합니다", "시청해 주셔서 감사합니다").
# 키오스크에서 손님이 할 일이 없는 말은 바로 버리고, "감사합니다"처럼 말할 수도 있는 짧은 말은 인식 확신이 낮을 때만 버린다.
_HALLUCINATION_ALWAYS = re.compile(r"시청해주셔서|시청해주신|구독과?좋아요|좋아요와?구독|자막제공|다음영상|mbc뉴스|한글자막|번역")
_HALLUCINATION_IF_UNSURE = {"감사합니다", "감사해요", "고맙습니다", "수고하셨습니다", "안녕히계세요", "안녕히가세요"}


def _is_hallucination(text: str, no_speech_prob: float, avg_logprob: float) -> bool:
    norm = re.sub(r"[\s.,!?~…]", "", text).lower()
    if not norm:
        return True
    if _HALLUCINATION_ALWAYS.search(norm):
        return True
    return norm in _HALLUCINATION_IF_UNSURE and (no_speech_prob > 0.4 or avg_logprob < -0.9)


def warmup() -> None:
    """서버 시작 시 모델을 메모리에 올리고 더미 오디오로 한 번 돌려 첫 요청 지연을 없앤다."""
    import numpy as np

    model = _load_model()
    segments, _ = model.transcribe(
        np.zeros(16000, dtype=np.float32), language="ko", beam_size=BEAM_SIZE, vad_filter=False
    )
    list(segments)  # 제너레이터를 소비해야 실제 디코딩이 실행된다


def transcribe(audio_path: str, language: str = "ko") -> str:
    model = _load_model()
    segments, _info = model.transcribe(
        audio_path,
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=BEAM_SIZE,
        initial_prompt=_VOCAB_PROMPT,
        condition_on_previous_text=False,  # 앞 문장이 다음 문장에 번지며 같은 말을 반복해 지어내는 것을 막는다
    )
    text = "".join(
        segment.text for segment in segments
        if not _is_hallucination(segment.text, segment.no_speech_prob, segment.avg_logprob)
    )
    return text.strip()
