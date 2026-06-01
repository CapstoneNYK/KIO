import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai.recommend import qa_chain
from ai.intent import classify_intent
from ai.entity import extract_entity
from app.ocr.router import router as ocr_router

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr_router)


class QueryRequest(BaseModel):
    query: str


@app.get("/")
def root():
    return {"msg": "hello"}


@app.post("/api/recommend")
async def ask_menu(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문이 비어있습니다.")

    answer = qa_chain.invoke(request.query)
    return {"question": request.query, "answer": answer}


@app.post("/api/ask")
async def ask_intent(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문이 비어있습니다.")

    intent = classify_intent(request.query)

    if intent == "order":
        entity = extract_entity(request.query)
        base_menu = None
        temperature = "ICE"

        if entity["menu"]:
            raw = entity["menu"]
            if raw.startswith("아이스 "):
                base_menu = raw[4:]
                temperature = "ICE"
            elif raw.startswith("핫 "):
                base_menu = raw[2:]
                temperature = "HOT"
            else:
                base_menu = raw
                temperature = "HOT" if "hot" in entity["attributes"] else "ICE"

        if base_menu:
            temp_str = "아이스" if temperature == "ICE" else "따뜻한"
            answer = f"{temp_str} {base_menu}을(를) 장바구니에 담았습니다."
        else:
            answer = "어떤 메뉴를 주문하시겠어요?"

        return {
            "question": request.query,
            "intent": "order",
            "answer": answer,
            "order": {
                "menu": base_menu,
                "temperature": temperature,
                "needs_recommendation": entity["needs_recommendation"],
            },
        }
    else:
        answer = qa_chain.invoke(request.query)
        return {"question": request.query, "intent": intent, "answer": answer}
