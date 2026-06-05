_METHOD_KEYWORDS: dict[str, str] = {
    "카카오페이": "kakao",
    "카카오": "kakao",
    "네이버페이": "naver",
    "네이버": "naver",
    "카드결제": "card",
    "카드": "card",
    "앱카드": "appcard",
    "모바일상품권": "voucher",
    "기프트카드": "giftcard",
    "기프트": "giftcard",
}

_METHOD_LABELS: dict[str, str] = {
    "kakao": "카카오페이",
    "naver": "네이버페이",
    "card": "카드결제",
    "appcard": "앱카드",
    "voucher": "모바일상품권",
    "giftcard": "기프트카드",
}


def extract_payment_method(query: str) -> str | None:
    for keyword, method in sorted(_METHOD_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword in query:
            return method
    return None


def get_payment_response(query: str) -> tuple[str, str | None]:
    method = extract_payment_method(query)
    if method:
        label = _METHOD_LABELS[method]
        return f"{label}로 결제를 진행할게요.", method
    return "결제를 진행할게요. 원하시는 결제수단을 선택해 주세요.", None
