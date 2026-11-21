# [discount.py] 현재 활성 할인 혜택을 한 줄 안내 문구로 만든다.
from ai import data_source


# 활성 할인 방식 이름들을 모아 '현재 … 할인 혜택을 받으실 수 있어요!' 문구 반환(할인이 없으면 None)
def get_discount_tip() -> str | None:
    discounts = data_source.get_discounts(active_only=True)
    if not discounts:
        return None
    methods = sorted({data_source.discount_methods()[d["method_code"]] for d in discounts})
    return f"현재 {', '.join(methods)} 할인 혜택을 받으실 수 있어요! 결제 시 선택해보세요."
