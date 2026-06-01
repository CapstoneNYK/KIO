from fastapi import APIRouter, HTTPException
from .mock_data import COUPONS

router = APIRouter(prefix="/api/coupon", tags=["coupon"])


@router.get("/scan")
async def scan_coupon(code: str):
    coupon = COUPONS.get(code.strip().upper())
    if not coupon:
        raise HTTPException(status_code=404, detail="유효하지 않은 쿠폰입니다.")
    return {"code": code.strip().upper(), **coupon}
