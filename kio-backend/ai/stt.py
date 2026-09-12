"""음성 인식(STT) 모듈.

기존에는 프론트엔드에서 브라우저 내장 Web Speech API(react-speech-recognition)를
그대로 사용했다. Web Speech API는 인식 로직을 커스터마이징할 수 없고, 카페처럼
배경 소음이 있는 환경에서 오인식이 잦다는 교수님 피드백이 있었다.

이 모듈은 faster-whisper(OpenAI Whisper를 CTranslate2로 최적화한 오픈소스 구현체)를
자체 서버에서 돌려서, 유료 API 없이도 노이즈에 더 강인한 STT를 제공한다.

- vad_filter=True: Silero VAD로 무음/잡음 구간을 먼저 걸러내고 음성 구간만 인식에 사용
  -> 배경 소음이 엉뚱한 텍스트로 잘못 인식되는 문제(할루시네이션)를 크게 줄여준다.
- 모델은 최초 요청 시 한 번만 로드해서 메모리에 유지한다(콜드 스타트 방지).
- 모델은 최초 실행 시 Hugging Face에서 자동 다운로드되며(인터넷 필요),
  이후에는 로컬 캐시로 오프라인 동작한다.

속도가 느리면 .env에서 아래 순서로 조정해보면 된다 (품질은 조금씩 떨어짐):
  1) WHISPER_BEAM_SIZE=1 (기본값, 이미 빠른 설정)
  2) WHISPER_MODEL_SIZE=base 또는 tiny (small보다 가벼움)
  3) WHISPER_CPU_THREADS를 CPU 코어 수에 맞게 올리기 (예: 8)
  4) (NVIDIA GPU가 있다면) WHISPER_DEVICE=cuda, WHISPER_COMPUTE_TYPE=float16
"""

import os
from functools import lru_cache

from faster_whisper import WhisperModel

# 사양이 낮은 PC에서도 돌아가도록 기본값은 int8 양자화 + small 모델로 설정.
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
# 0이면 ctranslate2가 알아서 코어 수를 결정. 느리면 실제 코어 수에 맞춰 올려볼 것.
CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "0"))
# beam_size가 클수록 정확하지만 느림. 실시간성이 중요한 키오스크라 기본을 1(그리디)로 낮춤.
BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))


@lru_cache(maxsize=1)
def _load_model() -> WhisperModel:
    return WhisperModel(
        MODEL_SIZE,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
        cpu_threads=CPU_THREADS,
    )


def transcribe(audio_path: str, language: str = "ko") -> str:
    """오디오 파일 경로를 받아 인식된 텍스트를 반환한다."""
    model = _load_model()
    segments, _info = model.transcribe(
        audio_path,
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        beam_size=BEAM_SIZE,
    )
    text = "".join(segment.text for segment in segments)
    return text.strip()
