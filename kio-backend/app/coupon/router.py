from fastapi import APIRouter, HTTPException
from app.admin import db

router = APIRouter(prefix="/api/coupon", tags=["coupon"])


@router.get("/scan")
def scan_coupon(code: str):
    coupon = db.get_coupon_by_code(code)
    if not coupon:
        raise HTTPException(status_code=404, detail="유효하지 않은 쿠폰입니다.")
    return coupon
