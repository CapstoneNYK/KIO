import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ai.recommend import qa_chain, recommend_chain
from ai.intent import classify_intent
from ai.entity import extract_multi_order
from ai.payment import get_payment_response
from ai.discount import get_discount_tip
from ai.order import apply_discount_menu_fallback, cart_answer, entities_to_orders, split_sold_out
from app.ocr.router import router as ocr_router
from app.ocr.db import get_all_discount_texts
from app.coupon.router import router as coupon_router
from app.admin import db as admin_db
from app.admin.db import UPLOAD_DIR
from app.admin.router import (
    router as admin_router,
    auth_router as admin_auth_router,
    menus_public_router,
    orders_router,
)

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_URL", "http://localhost:5173"),
        os.getenv("ADMIN_URL", "http://localhost:5174"),
        "http://localhost:5175",
        "http://localhost:5176",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr_router)
app.include_router(coupon_router)
app.include_router(admin_auth_router)
app.include_router(admin_router)
app.include_router(orders_router)
app.include_router(menus_public_router)

app.mount("/uploads/menu-images", StaticFiles(directory=UPLOAD_DIR), name="menu-images")


class QueryRequest(BaseModel):
    query: str
    cart_items: list[str] = []


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
        menus = admin_db.get_menus()
        menu_names = [m["name"] for m in menus]
        sold_out_names = {m["name"] for m in menus if m["sold_out"]}

        entities = extract_multi_order(request.query, menu_names)
        entities = apply_discount_menu_fallback(entities, request.query, menu_names)
        orders_all = entities_to_orders(entities)
        orders, sold_out = split_sold_out(orders_all, sold_out_names)

        named = [o for o in orders if o["menu"]]
        answer = cart_answer(named, sold_out)

        discount_tip: str | None = None
        if named:
            discount_texts = get_all_discount_texts()
            discount_tip = get_discount_tip(discount_texts)

        return {
            "question": request.query,
            "intent": "order",
            "answer": answer,
            "orders": orders,
            "discount_tip": discount_tip,
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
    elif intent == "order_and_pay":
        menus = admin_db.get_menus()
        menu_names = [m["name"] for m in menus]
        sold_out_names = {m["name"] for m in menus if m["sold_out"]}

        entities = extract_multi_order(request.query, menu_names)
        entities = apply_discount_menu_fallback(entities, request.query, menu_names)
        orders_all = entities_to_orders(entities)
        orders, sold_out = split_sold_out(orders_all, sold_out_names)

        named = [o for o in orders if o["menu"]]
        _, payment_method = get_payment_response(request.query)

        if sold_out and not named:
            # 담을 수 있는 메뉴가 없으면 결제 화면으로 넘어가지 않도록 일반 주문 응답으로 돌려준다
            return {
                "question": request.query,
                "intent": "order",
                "answer": cart_answer(named, sold_out),
                "orders": orders,
                "discount_tip": None,
            }

        method_label = {
            "card": "카드", "kakao": "카카오페이", "naver": "네이버페이",
            "appcard": "앱카드", "voucher": "모바일상품권", "giftcard": "기프트카드",
            "kt": "KT VIP", "tmembership": "T멤버십", "cjone": "CJ ONE", "uzu": "T우주",
        }.get(payment_method or "", "")
        suffix = f" {method_label}로 결제 화면으로 이동합니다." if method_label else " 결제 화면으로 이동합니다."

        return {
            "question": request.query,
            "intent": "order_and_pay",
            "answer": cart_answer(named, sold_out, pay_suffix=suffix),
            "orders": orders,
            "payment_method": payment_method,
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
        answer = qa_chain.invoke({"question": request.query, "cart_items": request.cart_items})
        return {"question": request.query, "intent": intent, "answer": answer}
