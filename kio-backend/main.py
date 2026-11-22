# [main.py] KIO 백엔드 진입점(FastAPI). 서버 설정(CORS·라우터)과 API 입구만 두고,
# 손님 말을 해석하는 로직은 ai/ 패키지에 있다.
#   요청 처리 본체  : ai/pipeline.py (handle_ask)  — '장바구니 명령 → 메모 → 바로 답하기 → 의도별 주문/추천/결제' 순서
#   이어 말하기     : ai/followup.py, 요청사항 메모 : ai/memo.py, LLM 없이 답하는 안내 : ai/quick_answers.py
#   세션별 대화 상태 : ai/session.py,  음성(STT/TTS) API : app/voice/router.py
import os
import time
import asyncio
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()  # ai.llm·ai.stt·app.admin.auth 가 import 시점에 환경변수를 읽으므로 다른 import 보다 먼저 불러온다

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ai.llm import warmup as warmup_llm
from ai.logging_utils import log_feedback, log_interaction
from ai.pipeline import handle_ask
from ai.stt import warmup as warmup_stt
from app.coupon.router import router as coupon_router
from app.voice.router import router as voice_router
from app.admin.db import UPLOAD_DIR
from app.admin.router import (
    router as admin_router,
    auth_router as admin_auth_router,
    discounts_public_router,
    menus_public_router,
    orders_router,
)


# 서버 시작 때 음성인식(STT)·LLM 모델을 미리 불러 첫 요청이 느려지지 않게 한다
def _warmup_models() -> None:
    t0 = time.perf_counter()
    try:
        warmup_stt()
    except Exception as e:
        print("[warmup] STT 워밍업 실패:", e)
    warmup_llm()
    print(f"[warmup] 모델 준비 완료 {(time.perf_counter() - t0) * 1000:.0f}ms")


# 서버가 켜질 때 워밍업을 끝낸 다음부터 요청을 받는다
@asynccontextmanager
async def _lifespan(_app: FastAPI):
    await asyncio.to_thread(_warmup_models)  # 워밍업이 끝난 뒤부터 요청을 받는다
    yield


app = FastAPI(lifespan=_lifespan)

# CORS: 프론트(5173)·관리자(5174) 주소만 허용. 개발용으로 localhost / 사설 IP 의 517x 포트도 정규식으로 허용
_frontend_urls = [u.strip() for u in os.getenv("FRONTEND_URL", "http://localhost:5173").split(",") if u.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_frontend_urls, os.getenv("ADMIN_URL", "http://localhost:5174")],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|100\.\d{1,3}\.\d{1,3}\.\d{1,3}):517[3-6]",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 쿠폰·관리자·주문·공개 메뉴/할인·음성 API 라우터 연결
app.include_router(coupon_router)
app.include_router(admin_auth_router)
app.include_router(admin_router)
app.include_router(orders_router)
app.include_router(menus_public_router)
app.include_router(discounts_public_router)
app.include_router(voice_router)

# 메뉴 이미지 업로드 폴더를 정적 파일로 제공
app.mount("/uploads/menu-images", StaticFiles(directory=UPLOAD_DIR), name="menu-images")


# /api/ask 요청 본문. dialog 는 서버가 저장하지 않고 프론트가 들고 다니며 되돌려 보내는 '옵션 되묻기 상태'.
# session_id: 키오스크(손님)별 상태 분리용. 프론트가 안 보내면 "" 하나를 공유해 예전처럼 동작한다.
class QueryRequest(BaseModel):
    query: str
    cart_items: list[str] = []
    dialog: dict | None = None  # 열려 있는 옵션 되묻기 대화 상태 (프론트가 되돌려 보냄)
    session_id: str = ""  # 키오스크/손님 구분값(프론트가 생성). 비우면 모두 같은 세션으로 취급


# ── API 엔드포인트 ──
# 헬스체크
@app.get("/")
def root():
    return {"msg": "hello"}


# 손님이 답변에 남기는 피드백(좋아요/싫어요) 저장용
class FeedbackRequest(BaseModel):
    query: str
    answer: str = ""
    intent: str | None = None


@app.post("/api/feedback", status_code=204)
def feedback(body: FeedbackRequest):
    log_feedback(body.query[:300], body.answer[:500], body.intent)


# ★ 메인 엔드포인트: 손님 말 한 줄 → 의도에 맞는 응답 JSON. 처리 결과는 항상 로그(log_interaction)에 남긴다
@app.post("/api/ask")
async def ask_intent(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문이 비어있습니다.")
    raw = request.query
    result = handle_ask(request.query, request.cart_items, request.dialog, request.session_id)
    log_interaction(raw, request.cart_items, result)
    return result
