import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from app.admin import db
from app.admin.db import UPLOAD_DIR
from app.admin.auth import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    create_access_token,
    get_current_admin,
    register_admin,
    verify_admin_credentials,
)

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])

auth_router = APIRouter(prefix="/api/admin", tags=["admin-auth"])


# ── Auth ───────────────────────────────────────────────────────────────────

@auth_router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest):
    if not verify_admin_credentials(body.username, body.password):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    return TokenResponse(access_token=create_access_token(body.username))


@auth_router.post("/signup", status_code=201, response_model=TokenResponse)
def signup(body: SignupRequest):
    register_admin(body)
    return TokenResponse(access_token=create_access_token(body.username))


# ── Menus ──────────────────────────────────────────────────────────────────

class MenuCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    price: int = Field(ge=0)
    category: str
    temps: list[str] = []
    image_url: str | None = None


class MenuUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    price: int | None = Field(default=None, ge=0)
    category: str | None = None
    temps: list[str] | None = None
    sold_out: bool | None = None
    image_url: str | None = None


ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


def _delete_image_file(image_url: str | None) -> None:
    if not image_url or not image_url.startswith("/uploads/menu-images/"):
        return
    path = UPLOAD_DIR / image_url.rsplit("/", 1)[-1]
    path.unlink(missing_ok=True)


@router.post("/uploads/menu-image")
async def upload_menu_image(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="jpg/png/webp/gif 이미지만 업로드할 수 있습니다.")
    contents = await file.read()
    if len(contents) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=400, detail="이미지 용량은 5MB 이하여야 합니다.")
    filename = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / filename).write_bytes(contents)
    return {"image_url": f"/uploads/menu-images/{filename}"}


@router.get("/menus")
def list_menus():
    return db.get_menus()


@router.post("/menus", status_code=201)
def create_menu(body: MenuCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="메뉴명을 입력해주세요.")
    if db.menu_name_exists(name):
        raise HTTPException(status_code=409, detail="이미 존재하는 메뉴명입니다.")
    return db.create_menu(name, body.price, body.category, body.temps, body.image_url)


@router.put("/menus/{menu_id}")
def update_menu(menu_id: int, body: MenuUpdate):
    existing = db.get_menu(menu_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    fields = body.model_dump(exclude_none=True)
    if "name" in fields:
        fields["name"] = fields["name"].strip()
        if not fields["name"]:
            raise HTTPException(status_code=422, detail="메뉴명을 입력해주세요.")
        if db.menu_name_exists(fields["name"], exclude_id=menu_id):
            raise HTTPException(status_code=409, detail="이미 존재하는 메뉴명입니다.")
    result = db.update_menu(menu_id, **fields) or existing
    if body.image_url is not None and existing["image_url"] != body.image_url:
        _delete_image_file(existing["image_url"])
    return result


@router.delete("/menus/{menu_id}", status_code=204)
def delete_menu(menu_id: int):
    existing = db.get_menu(menu_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="메뉴를 찾을 수 없습니다.")
    db.delete_menu(menu_id)
    _delete_image_file(existing["image_url"])


# ── Discounts ──────────────────────────────────────────────────────────────

_ALLOWED_METHOD_CODES = set(db.DISCOUNT_METHODS.keys())


class DiscountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    method_code: str
    description: str = Field(default="", max_length=2000)
    active: bool = True
    image_url: str | None = None

    @field_validator("method_code")
    @classmethod
    def validate_method_code(cls, v: str) -> str:
        if v not in _ALLOWED_METHOD_CODES:
            raise ValueError(f"method_code는 {sorted(_ALLOWED_METHOD_CODES)} 중 하나여야 합니다.")
        return v


class DiscountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    method_code: str | None = None
    description: str | None = Field(default=None, max_length=2000)
    active: bool | None = None
    image_url: str | None = None

    @field_validator("method_code")
    @classmethod
    def validate_method_code(cls, v: str | None) -> str | None:
        if v is not None and v not in _ALLOWED_METHOD_CODES:
            raise ValueError(f"method_code는 {sorted(_ALLOWED_METHOD_CODES)} 중 하나여야 합니다.")
        return v


@router.get("/discounts")
def list_discounts():
    return db.get_discounts()


@router.post("/discounts", status_code=201)
def create_discount(body: DiscountCreate):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="할인 이름을 입력해주세요.")
    return db.create_discount(name, body.method_code, body.description.strip(), body.active, body.image_url)


@router.put("/discounts/{discount_id}")
def update_discount(discount_id: int, body: DiscountUpdate):
    existing = db.get_discount(discount_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="할인 혜택을 찾을 수 없습니다.")
    fields = body.model_dump(exclude_none=True)
    if "name" in fields:
        fields["name"] = fields["name"].strip()
        if not fields["name"]:
            raise HTTPException(status_code=422, detail="할인 이름을 입력해주세요.")
    if "description" in fields:
        fields["description"] = fields["description"].strip()
    result = db.update_discount(discount_id, **fields) or existing
    if body.image_url is not None and existing["image_url"] != body.image_url:
        _delete_image_file(existing["image_url"])
    return result


@router.delete("/discounts/{discount_id}", status_code=204)
def delete_discount(discount_id: int):
    existing = db.get_discount(discount_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="할인 혜택을 찾을 수 없습니다.")
    db.delete_discount(discount_id)
    _delete_image_file(existing["image_url"])


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


# kio-frontend가 호출하는 엔드포인트 (prefix 없이 /api/orders, /api/menus, /api/discounts)
orders_router = APIRouter(prefix="/api", tags=["orders"])
menus_public_router = APIRouter(prefix="/api", tags=["menus"])
discounts_public_router = APIRouter(prefix="/api", tags=["discounts"])


@menus_public_router.get("/menus")
def list_menus_public():
    return db.get_menus()


@discounts_public_router.get("/discounts")
def list_discounts_public():
    return db.get_discounts(active_only=True)


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


@router.get("/sales/trend")
def get_sales_trend(period: str = "today"):
    if period not in ("today", "week", "month"):
        raise HTTPException(status_code=400, detail="period는 today/week/month 중 하나여야 합니다.")
    return db.get_sales_trend(period)


@router.get("/analytics")
def get_analytics():
    return db.get_analytics()
