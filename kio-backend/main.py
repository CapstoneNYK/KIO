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
from app.ocr.router import router as ocr_router
from app.ocr.db import get_all_menu_texts, get_all_discount_texts
from app.coupon.router import router as coupon_router
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
        ocr_menus = get_all_menu_texts()
        entities = extract_multi_order(request.query, ocr_menus)

        # 할인 수단 언급 + 메뉴 미추출(또는 단음절 오인식) 시 할인 대상 메뉴로 보완
        _DISCOUNT_MENU_MAP = {
            "T멤버십": ("아메리카노", None),   # None = 온도 그대로 (ICE/HOT 무관)
            "tmembership": ("아메리카노", None),
        }
        def _is_noise_menu(menu: str | None) -> bool:
            if not menu:
                return True
            cleaned = menu.strip()
            # 단음절이거나 할인 키워드 앞글자(T, KT 등) 오인식
            if len(cleaned) <= 2:
                return True
            if cleaned.upper() in ("T", "KT", "CJ", "SKT"):
                return True
            return False

        if all(_is_noise_menu(e.get("menu")) for e in entities):
            q_norm = request.query.replace(" ", "")
            for keyword, (menu, temp) in _DISCOUNT_MENU_MAP.items():
                if keyword.replace(" ", "") in q_norm:
                    resolved_temp = temp if temp else "ICE"
                    entities = [{"menu": menu, "quantity": 1, "temperature": resolved_temp,
                                 "options": [], "attributes": [], "needs_recommendation": False}]
                    break

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
                "options": entity.get("options", []),
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
                "options": entity.get("options", []),
                "needs_recommendation": entity["needs_recommendation"],
            })

        named = [o for o in orders if o["menu"]]
        _, payment_method = get_payment_response(request.query)

        if named:
            items_str = ", ".join(
                f"{'아이스' if o['temperature'] == 'ICE' else '따뜻한'} {o['menu']}"
                for o in named
            )
            method_label = {
                "card": "카드", "kakao": "카카오페이", "naver": "네이버페이",
                "appcard": "앱카드", "voucher": "모바일상품권", "giftcard": "기프트카드",
                "kt": "KT VIP", "tmembership": "T멤버십", "cjone": "CJ ONE", "uzu": "T우주",
            }.get(payment_method or "", "")
            suffix = f" {method_label}로 결제 화면으로 이동합니다." if method_label else " 결제 화면으로 이동합니다."
            answer = f"{items_str}을(를) 장바구니에 담고{suffix}"
        else:
            answer = "어떤 메뉴를 주문하시겠어요?"

        return {
            "question": request.query,
            "intent": "order_and_pay",
            "answer": answer,
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
