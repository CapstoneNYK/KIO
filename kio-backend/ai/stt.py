"""음성 인식(STT) 모듈.

기존에는 프론트엔드에서 브라우저 내장 Web Speech API(react-speech-recognition)를
그대로 사용했다. Web Speech API는 인식 로직을 커스터마이징할 수 없고, 카페처럼
배경 소음이 있는 환경에서 오인식이 잦다는 교수님 피드백이 있었다.

이 모듈은 faster-whisper(OpenAI Whisper를 CTranslate2로 최적화한 오픈소스 구현체)를
자체 서버에서 돌려서, 유료 API 없이도 노이즈에 더 강인한 STT를 제공한다.

- vad_filter=True: Silero VAD로 무음/잡음 구간을 먼저 걸러내고 음성 구간만 인식에 사용
  -> 배경 소음이 엉뚱한 텍스트로 잘못 인식되는 문제(할루시네이션)를 크게 줄여준다.
- initial_prompt: 학습(파인튜닝) 없이도, 우리 카페 메뉴/결제수단 이름과 대표적인
  주문 말투 예시를 미리 "힌트"로 던져줘서, 애매한 발음이 메뉴명/주문 말투 쪽으로
  인식되도록 유도한다. (예: "줘"가 더 흔한 "죠"로 오인식되는 걸 줄여줌)
- 모델은 최초 요청 시 한 번만 로드해서 메모리에 유지한다(콜드 스타트 방지).
- 모델은 최초 실행 시 Hugging Face에서 자동 다운로드되며(인터넷 필요),
  이후에는 로컬 캐시로 오프라인 동작한다.

속도가 느리면 .env에서 아래 순서로 조정해보면 된다 (품질은 조금씩 떨어짐):
  1) WHISPER_BEAM_SIZE=1 (기본값, 이미 빠른 설정)
  2) WHISPER_MODEL_SIZE=base 또는 tiny (small보다 가벼움)
  3) WHISPER_CPU_THREADS를 CPU 코어 수에 맞게 올리기 (예: 8)
  4) (NVIDIA GPU가 있다면) WHISPER_DEVICE=cuda, WHISPER_COMPUTE_TYPE=float16

참고: initial_prompt/어휘 힌트로도 한계는 있다. Whisper는 범용 모델이라 짧고
뭉개진 명령형 어미("~줘")나 "1번/2번" 같은 숫자+단위 표현을 다른 표현으로
잘못 인식하는 경우가 남아있을 수 있는데, 이건 프롬프트 트릭만으로 완전히
없애기 어렵고 실제 파인튜닝(문서 data/README.md 참고)이 필요한 영역이다.

주의(중요): 이 파일이 과거에 두 번 정도 이전 버전으로 되돌아가 있는 걸 발견한
적이 있다(원인 추정: 커밋 안 된 변경사항이 git 작업 중 날아감). 이 파일을 손으로
고칠 때는 반드시 `git add ai/stt.py && git commit`으로 바로 커밋해두는 걸 권장.
"""

import os
from functools import lru_cache

from faster_whisper import WhisperModel

from ai.dictionary import MENU_KEYWORDS

# 사양이 낮은 PC에서도 돌아가도록 기본값은 int8 양자화 + small 모델로 설정.
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
# 0이면 ctranslate2가 알아서 코어 수를 결정. 느리면 실제 코어 수에 맞춰 올려볼 것.
CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "0"))
# beam_size가 클수록 정확하지만 느림. 실시간성이 중요한 키오스크라 기본을 1(그리디)로 낮춤.
BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "1"))

# 메뉴명 외에 자주 오인식되는 결제/할인 수단 이름 (dictionary.py엔 없는 것만 추가)
_EXTRA_VOCAB = [
    "카드결제", "카카오페이", "네이버페이", "앱카드", "모바일상품권", "기프트카드",
    "KT VIP", "T멤버십", "CJ ONE", "T우주", "우주패스", "쿠폰",
]

# 명령형 어미("~줘", "~주세요" 등)나 "1번/2번" 같은 순서 참조 표현이 다른 표현으로
# 오인식되는 걸 줄이기 위해, 실제 주문할 때 쓰는 말투를 문장 예시로 몇 개 넣어준다.
# 단어 나열보다 문장 형태가 Whisper에게 "이런 말투/어미가 나올 확률이 높다"는
# 문맥으로 더 잘 작동한다.
_STYLE_EXAMPLES = [
    "아메리카노 한 잔 줘",
    "카페라떼 두 잔 주세요",
    "바닐라라떼 하나 담아줘",
    "이거 주문할게요",
    "그 중에 1번으로 두 잔 줘",
    "2번 메뉴로 담아줘",
]


def _build_vocabulary_prompt() -> str:
    """메뉴명/결제수단/주문 말투 예시를 Whisper의 initial_prompt로 넘길 문자열로 만든다.

    학습 데이터 없이도, 도메인 어휘와 말투를 미리 알려주는 것만으로 인식 정확도를
    끌어올릴 수 있는 무료 트릭이다 (파인튜닝 없이 바로 적용 가능).
    """
    menus = sorted(set(MENU_KEYWORDS.values()))
    vocab_line = ", ".join(menus + _EXTRA_VOCAB)
    style_line = " ".join(_STYLE_EXAMPLES)
    return f"{vocab_line}. {style_line}"


# 어휘 목록은 고정 데이터라 앱 시작 시 한 번만 만들어 재사용한다.
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
    """오디오 파일 경로를 받아 인식된 텍스트를 반환한다."""
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
