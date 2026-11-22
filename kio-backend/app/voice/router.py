# [voice/router.py] 음성 API: 음성 → 글자(STT, /api/stt), 글자 → 음성(TTS, /api/tts). main.py 에서 분리했다.
import os
import tempfile

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from ai.stt import transcribe as transcribe_audio

router = APIRouter()

# 음성 → 글자(STT). 업로드한 오디오를 임시 파일에 저장해 faster-whisper 로 인식하고, 끝나면 지운다
@router.post("/api/stt")
async def speech_to_text(file: UploadFile = File(...)):
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="오디오 데이터가 비어있습니다.")

    suffix = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        text = transcribe_audio(tmp_path, language="ko")
    finally:
        os.unlink(tmp_path)

    if not text:
        raise HTTPException(status_code=422, detail="음성을 인식하지 못했습니다. 다시 말씀해 주세요.")

    return {"text": text}


# 글자 → 음성(TTS, edge-tts). 같은 문장은 메모리 캐시(최대 200개)에서 바로 돌려준다
_TTS_CACHE: dict[str, bytes] = {}


TTS_VOICE = os.getenv("TTS_VOICE", "ko-KR-SunHiNeural")


TTS_RATE = os.getenv("TTS_RATE", "+8%")


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=400)


# TTS 요청 처리: 캐시 → edge-tts 합성 → 실패 시 503
@router.post("/api/tts")
async def text_to_speech(body: TTSRequest):
    text = body.text.strip()
    if text in _TTS_CACHE:
        return Response(_TTS_CACHE[text], media_type="audio/mpeg")
    try:
        import edge_tts
    except ImportError:
        raise HTTPException(status_code=503, detail="edge-tts가 설치되지 않았습니다.")
    try:
        chunks = [c["data"] async for c in edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE).stream()
                  if c["type"] == "audio"]
    except Exception:
        raise HTTPException(status_code=503, detail="음성 합성 서버에 연결하지 못했습니다.")
    if not chunks:
        raise HTTPException(status_code=503, detail="음성을 만들지 못했습니다.")
    audio = b"".join(chunks)
    if len(_TTS_CACHE) < 200:
        _TTS_CACHE[text] = audio
    return Response(audio, media_type="audio/mpeg")
