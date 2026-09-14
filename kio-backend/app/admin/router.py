from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.admin import db

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Menus ──────────────────────────────────────────────────────────────────

class MenuCreate(BaseModel):
    name: str
    price: int
    category: str
    temps: list[str] = []


class MenuUpdate(BaseModel):
    name: str | None = None
    price: int | None = None
    category: str | None = None
    temps: list[str] | None = None
    sold_out: bool | None = None


@router.get("/menus")
def list_menus():
    return db.get_menus()


@router.post("/menus", status_code=201)
def create_menu(body: MenuCreate):
    return db.create_menu(body.name, body.price, body.category, body.temps)


@router.put("/menus/{menu_id}")
def update_menu(menu_id: int, body: MenuUpdate):
    result = db.update_menu(menu_id, **body.model_dump(exclude_none=True))
    if result is None:
        raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    return result


@router.delete("/menus/{menu_id}", status_code=204)
def delete_menu(menu_id: int):
    if not db.delete_menu(menu_id):
        raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")


# ── Orders ─────────────────────────────────────────────────────────────────

class OrderItem(BaseModel):
    menu_name: str
    temperature: str = ""
    quantity: int
    unit_price: int
    is_free: bool = False


class OrderCreate(BaseModel):
    payment_method: str
    total_amount: int
    discount_amount: int = 0
    final_amount: int
    is_packaging: bool = False
    items: list[OrderItem]


# kio-frontend가 호출하는 엔드포인트 (prefix 없이 /api/orders)
orders_router = APIRouter(prefix="/api", tags=["orders"])


@orders_router.post("/orders", status_code=201)
def create_order(body: OrderCreate):
    return db.save_order(
        payment_method=body.payment_method,
        total_amount=body.total_amount,
        discount_amount=body.discount_amount,
        final_amount=body.final_amount,
        is_packaging=body.is_packaging,
        items=[i.model_dump() for i in body.items],
    )


@router.get("/orders")
def list_orders(date_from: str | None = None, date_to: str | None = None):
    return db.get_orders(date_from, date_to)


# ── Sales & Analytics ──────────────────────────────────────────────────────

@router.get("/sales")
def get_sales(period: str = "today"):
    if period not in ("today", "week", "month"):
        raise HTTPException(status_code=400, detail="period는 today/week/month 중 하나여야 합니다.")
    return db.get_sales(period)


@router.get("/analytics")
def get_analytics():
    return db.get_analytics()
