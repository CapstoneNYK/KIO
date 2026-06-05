import re

_ACTION_KEYWORDS: dict[str, str] = {
    "처음으로": "home",
    "전체": "all",
    "결제": "payment",
    "주문": "order",
    "담기": "add_to_cart",
    "장바구니": "cart",
    "취소": "cancel",
    "확인": "confirm",
    "삭제": "delete",
    "추가": "add",
    "선택": "select",
    "완료": "complete",
    "닫기": "close",
    "뒤로": "back",
    "이전": "back",
    "다음": "next",
    "홈": "home",
}

_PRICE_PATTERN = re.compile(r"^\d[\d,\.]*원?$")

def _classify_text(text: str) -> dict:
    stripped = text.strip()
    for keyword, subtype in _ACTION_KEYWORDS.items():
        if keyword in stripped:
            return {"label": "action_button", "subtype": subtype}
    if _PRICE_PATTERN.match(stripped.replace(" ", "")):
        return {"label": "price"}
    if stripped:
        return {"label": "menu_item"}
    return {"label": "unknown"}

def classify_ocr_results(ocr_items: list[dict]) -> list[dict]:
    return [{**item, **_classify_text(item["text"])} for item in ocr_items]
