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
    # 주의: "KT 멤버십"을 공백 제거+소문자화하면 "kt멤버십"이 되는데, 이 안에는
    # 아래 "T멤버십"(SKT) 키워드가 부분 문자열로 그대로 들어있다("kt멤버십"의 뒤 4글자
    # = "t멤버십"). 매칭 로직이 "긴 키워드 우선"이라 길이가 같으면 딕셔너리에 먼저
    # 등록된 T멤버십 쪽이 먼저 매칭되어, "KT 멤버십 할게"가 SKT 계열인 T멤버십으로
    # 잘못 인식되는 버그가 있었다. "KT멤버십"처럼 더 긴 키워드를 명시해서 먼저
    # 매칭되게 하여 해결한다.
    "KT멤버십": "kt",
    "kt멤버십": "kt",
    "케이티멤버십": "kt",
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
