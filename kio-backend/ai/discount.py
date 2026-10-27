from app.admin import db


def get_discount_tip() -> str | None:
    discounts = db.get_discounts(active_only=True)
    if not discounts:
        return None
    methods = sorted({db.DISCOUNT_METHODS[d["method_code"]] for d in discounts})
    return f"현재 {', '.join(methods)} 할인 혜택을 받으실 수 있어요! 결제 시 선택해보세요."
