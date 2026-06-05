_METHOD_KEYWORDS: dict[str, str] = {
    # 결제수단 (긴 키워드 먼저)
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
    # 할인수단
    "KT VIP": "kt",
    "kt vip": "kt",
    "케이티": "kt",
    "KT": "kt",
    "kt": "kt",
    "T멤버십": "tmembership",
    "티멤버십": "tmembership",
    "t멤버십": "tmembership",
    "CJ ONE": "cjone",
    "cj one": "cjone",
    "씨제이원": "cjone",
    "CJ": "cjone",
    "cj": "cjone",
    "T우주": "uzu",
    "t우주": "uzu",
    "티우주": "uzu",
    "우주패스": "uzu",
}

_METHOD_LABELS: dict[str, str] = {
    "kakao": "카카오페이",
    "naver": "네이버페이",
    "card": "카드결제",
    "appcard": "앱카드",
    "voucher": "모바일상품권",
    "giftcard": "기프트카드",
    "kt": "KT VIP 초이스",
    "tmembership": "T 멤버십",
    "cjone": "CJ ONE",
    "uzu": "T우주 우주패스",
}


def extract_payment_method(query: str) -> str | None:
    query_norm = query.replace(" ", "").lower()
    for keyword, method in sorted(_METHOD_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword.replace(" ", "").lower() in query_norm:
            return method
    return None


def get_payment_response(query: str) -> tuple[str, str | None]:
    method = extract_payment_method(query)
    if method:
        label = _METHOD_LABELS[method]
        return f"{label}로 결제를 진행할게요.", method
    return "결제를 진행할게요. 원하시는 결제수단을 선택해 주세요.", None
