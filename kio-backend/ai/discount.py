# OCR 오인식을 고려한 부분 매칭 패턴 (keyword → method)
_DISCOUNT_PATTERNS: list[tuple[str, str]] = [
    ("T멤버십", "T멤버십"),
    ("멤버십", "T멤버십"),   # OCR이 앞글자 오인식해도 "멤버십"은 보통 살아남음
    ("T-PASS", "T멤버십"),
    ("TPASS", "T멤버십"),
    ("T우주", "T우주"),
    ("우주패스", "T우주"),
    ("KT VIP", "KT VIP"),
    ("KT", "KT VIP"),
    ("CJ ONE", "CJ ONE"),
    ("CJONE", "CJ ONE"),
]

# 할인 정보가 있다는 신호 키워드 (방법명 특정 불가 시 fallback용)
_DISCOUNT_SIGNAL_KEYWORDS = ["할인", "혜택", "적립", "무료"]


def get_discount_tip(grouped: dict[str, list[str]]) -> str | None:
    if not grouped:
        return None

    all_texts = [t for texts in grouped.values() for t in texts]
    combined = " ".join(all_texts).upper()

    found: set[str] = set()
    for keyword, method in _DISCOUNT_PATTERNS:
        if keyword.upper() in combined:
            found.add(method)

    if found:
        methods = ", ".join(sorted(found))
        return f"현재 {methods} 할인 혜택을 받으실 수 있어요! 결제 시 선택해보세요."

    if any(kw in " ".join(all_texts) for kw in _DISCOUNT_SIGNAL_KEYWORDS):
        return "할인 혜택을 받으실 수 있어요! 결제 시 할인 수단을 확인해보세요."

    return None
