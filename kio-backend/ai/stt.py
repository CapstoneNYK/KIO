"""음성 인식(STT) 모듈.

기존에는 프론트엔드에서 브라우저 내장 Web Speech API(react-speech-recognition)를
그대로 사용했다. Web Speech API는 인식 로직을 커스터마이징할 수 없고, 카페처럼
배경 소음이 있는 환경에서 오인식이 잦다는 교수님 피드백이 있었다.

이 모듈은 faster-whisper(OpenAI Whisper를 CTranslate2로 최적화한 오픈소스 구현체)를
자체 서버에서 돌려서, 유료 API 없이도 노이즈에 더 강인한 STT를 제공한다.

- vad_filter=True: Silero VAD로 무음/잡음 구간을 먼저 걸러내고 음성 구간만 인식에 사용
  -> 배경 소음이 엉뚱한 텍스트로 잘못 인식되는 문제(할루시네이션)를 크게 줄여준다.
- initial_prompt: 학습(파인튜닝) 없이도, 우리 카페 메뉴/결제수단 이름을 미리
  "힌트"로 던져줘서 애매한 발음이 메뉴명 쪽으로 인식되도록 유도한다.
  (예: "카페라 때"로 잘못 들릴 발음도 힌트 덕분에 "카페라떼"로 인식될 확률이 올라감)
- 모델은 최초 요청 시 한 번만 로드해서 메모리에 유지한다(콜드 스타트 방지).
- 모델은 최초 실행 시 Hugging Face에서 자동 다운로드되며(인터넷 필요),
  이후에는 로컬 캐시로 오프라인 동작한다.
"""

import os
from functools import lru_cache

from faster_whisper import WhisperModel

from ai.dictionary import MENU_KEYWORDS

# 사양이 낮은 PC에서도 돌아가도록 기본값은 int8 양자화 + small 모델로 설정.
# .env에서 WHISPER_MODEL_SIZE / WHISPER_COMPUTE_TYPE / WHISPER_DEVICE로 조정 가능.
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")

# 메뉴명 외에 자주 오인식되는 결제/할인 수단 이름 (dictionary.py엔 없는 것만 추가)
_EXTRA_VOCAB = [
    "카드결제", "카카오페이", "네이버페이", "앱카드", "모바일상품권", "기프트카드",
    "KT VIP", "T멤버십", "CJ ONE", "T우주", "우주패스", "쿠폰",
]


def _build_vocabulary_prompt() -> str:
    """메뉴명/결제수단 목록을 Whisper의 initial_prompt로 넘길 문자열로 만든다.

    학습 데이터 없이도, 도메인 어휘를 미리 알려주는 것만으로 인식 정확도를
    끌어올릴 수 있는 무료 트릭이다 (파인튜닝 없이 바로 적용 가능).
    """
    menus = sorted(set(MENU_KEYWORDS.values()))
    return ", ".join(menus + _EXTRA_VOCAB)


# 어휘 목록은 고정 데이터라 앱 시작 시 한 번만 만들어 재사용한다.
_VOCAB_PROMPT = _build_vocabulary_prompt()


@lru_cache(maxsize=1)
def _load_model() -> WhisperModel:
    return WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)


def transcribe(audio_path: str, language: str = "ko") -> str:
    """오디오 파일 경로를 받아 인식된 텍스트를 반환한다."""
    model = _load_model()
    segments, _info = model.transcribe(
        audio_path,
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=5,
        initial_prompt=_VOCAB_PROMPT,
    )
    text = "".join(segment.text for segment in segments)
    return text.strip()
