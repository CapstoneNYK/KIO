import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai.recommend import qa_chain, recommend_chain
from ai.intent import classify_intent
from ai.entity import extract_multi_order
from ai.payment import get_payment_response
from app.ocr.router import router as ocr_router
from app.ocr.db import get_all_menu_texts
from app.coupon.router import router as coupon_router

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
app.include_router(coupon_router)


class QueryRequest(BaseModel):
    query: str


@app.get("/")
def root():
    return {"msg": "hello"}


@app.post("/api/recommend")
async def ask_menu(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문이 비어있습니다.")

    result = recommend_chain.invoke(request.query)
    return {"question": request.query, "answer": result.answer, "recommended_menus": result.menus}


@app.post("/api/ask")
async def ask_intent(request: QueryRequest):
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="질문이 비어있습니다.")

    intent = classify_intent(request.query)

    if intent == "order":
        ocr_menus = get_all_menu_texts()
        entities = extract_multi_order(request.query, ocr_menus)

        orders = []
        for entity in entities:
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
            orders.append({
                "menu": base_menu,
                "temperature": temperature,
                "quantity": entity["quantity"],
                "needs_recommendation": entity["needs_recommendation"],
            })

        named = [o for o in orders if o["menu"]]
        if named:
            items_str = ", ".join(
                f"{'아이스' if o['temperature'] == 'ICE' else '따뜻한'} {o['menu']}"
                for o in named
            )
            answer = f"{items_str}을(를) 장바구니에 담았습니다."
        else:
            answer = "어떤 메뉴를 주문하시겠어요?"

        return {
            "question": request.query,
            "intent": "order",
            "answer": answer,
            "orders": orders,
        }
    elif intent == "coupon":
        return {
            "question": request.query,
            "intent": "coupon",
            "answer": "쿠폰 바코드를 카메라로 스캔해볼게요!",
        }
    elif intent == "recommend":
        result = recommend_chain.invoke(request.query)
        return {
            "question": request.query,
            "intent": intent,
            "answer": result.answer,
            "recommended_menus": result.menus,
        }
    elif intent == "payment":
        answer, payment_method = get_payment_response(request.query)
        return {
            "question": request.query,
            "intent": "payment",
            "answer": answer,
            "payment_method": payment_method,
        }
    else:
        answer = qa_chain.invoke(request.query)
        return {"question": request.query, "intent": intent, "answer": answer}
