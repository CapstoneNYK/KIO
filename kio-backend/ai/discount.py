from app.admin import db


def get_discount_tip() -> str | None:
    """주문 직후 보여줄 힌트. 활성화된 할인의 결제수단을 그대로 안내한다."""
    discounts = db.get_discounts(active_only=True)
    if not discounts:
        return None
    methods = sorted({db.DISCOUNT_METHODS[d["method_code"]] for d in discounts})
    return f"현재 {', '.join(methods)} 할인 혜택을 받으실 수 있어요! 결제 시 선택해보세요."
