# 결제수단 키워드 → 코드. 비교할 때 소문자·공백 제거를 하므로 'KT'/'kt', 'CJ ONE'/'cj one' 같은 대소문자 중복 항목은 사실상 같은 항목이다.
# 긴 키워드가 먼저 검사되도록 extract_payment_method 에서 길이 내림차순으로 정렬한다(예: '앱카드'가 '카드'보다 먼저).
# [payment.py] 말 속에서 결제수단(카카오페이·카드·KT 등)을 찾아 안내 문구를 만든다.
import re

_METHOD_KEYWORDS: dict[str, str] = {
    "카카오페이": "kakao",
    "카카오": "kakao",
    "네이버페이": "naver",
    "네이버": "naver",
    "카드결제": "card",
    "카드": "card",
    "앱카드": "appcard",
    "삼성페이": "appcard",
    "애플페이": "appcard",
    "구글페이": "appcard",
    "삼성월렛": "appcard",
    "모바일상품권": "voucher",
    "기프트카드": "giftcard",
    "기프트": "giftcard",
    "KT VIP": "kt",
    "케이티": "kt",
    "KT": "kt",
    "KT멤버십": "kt",
    "케이티멤버십": "kt",
    "T멤버십": "tmembership",
    "티멤버십": "tmembership",
    "CJ ONE": "cjone",
    "씨제이원": "cjone",
    "CJ": "cjone",
    "T우주": "uzu",
    "티우주": "uzu",
    "우주패스": "uzu",
}

# 결제수단 코드 → 정식 이름
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


# 안내 문장에 쓰는 짧은 이름 ("카드로 결제 화면으로 이동합니다")
# 결제수단 코드 → 안내 문장용 짧은 이름
_SHORT_LABELS: dict[str, str] = {
    "card": "카드", "kakao": "카카오페이", "naver": "네이버페이",
    "appcard": "앱카드", "voucher": "모바일상품권", "giftcard": "기프트카드",
    "kt": "KT VIP", "tmembership": "T멤버십", "cjone": "CJ ONE", "uzu": "T우주",
}


# 삼성페이·애플페이 등 모바일 페이 언급(앱카드로 안내하기 위함)
_RE_MOBILE_PAY = re.compile(r"삼성페이|애플페이|구글페이|삼성월렛")


# 결제수단 코드 → 짧은 이름(없으면 빈 문자열)
def payment_label(method: str | None) -> str:
    return _SHORT_LABELS.get(method or "", "")


# 말 속에서 결제수단 코드를 찾는다. 긴 키워드 우선, 못 찾으면 None
def extract_payment_method(query: str) -> str | None:
    query_norm = query.replace(" ", "").lower()
    for keyword, method in sorted(_METHOD_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if keyword.replace(" ", "").lower() in query_norm:
            return method
    return None


# 결제 안내 문구와 결제수단 코드를 반환. 삼성페이/애플페이는 앱카드로 안내, 수단이 없으면 선택하라고 안내
def get_payment_response(query: str) -> tuple[str, str | None]:
    method = extract_payment_method(query)
    if method:
        label = _METHOD_LABELS[method]
        if method == "appcard" and _RE_MOBILE_PAY.search(query.replace(" ", "")):
            return "삼성페이·애플페이는 앱카드로 결제하시면 돼요. 앱카드로 결제를 진행할게요.", method
        return f"{label}로 결제를 진행할게요.", method
    return "결제를 진행할게요. 원하시는 결제수단을 선택해 주세요.", None
