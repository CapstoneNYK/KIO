import re
from typing import Dict, Optional
from dictionary import MENU_KEYWORDS, ATTRIBUTE_KEYWORDS

# 텍스트 정리
def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    return text


# 메뉴 추출
def extract_menu(text: str) -> Optional[str]:
    text = normalize_text(text)

    sorted_keys = sorted(MENU_KEYWORDS.keys(), key=len, reverse=True)

    for key in sorted_keys:
        if normalize_text(key) in text:
            return MENU_KEYWORDS[key]

    return None


# 속성 추출
def extract_attributes(text: str):
    text = normalize_text(text)
    attrs = []

    for key, value in ATTRIBUTE_KEYWORDS.items():
        if normalize_text(key) in text:
            attrs.append(value)

    return attrs


# OCR 매칭
def match_menu_with_ocr(menu: str, ocr_menus: list) -> Optional[str]:
    if not menu:
        return None

    menu_norm = normalize_text(menu)

    for ocr_menu in ocr_menus:
        ocr_norm = normalize_text(ocr_menu)

        if ocr_norm in menu_norm or menu_norm in ocr_norm:
            return ocr_menu

    return None


# 최종 엔티티 추출
def extract_entity(text: str, ocr_menus: list = None) -> Dict:
    menu = extract_menu(text)
    attrs = extract_attributes(text)

    # 메뉴 없으면 추천으로 넘김
    if not menu:
        return {
            "menu": None,
            "attributes": attrs,
            "needs_recommendation": True,
            "matched_menu": None,
            "confidence": 0.0
        }

    # 온도 적용
    if "ice" in attrs:
        menu = "아이스 " + menu
    elif "hot" in attrs:
        menu = "핫 " + menu

    matched_menu = None
    if ocr_menus:
        matched_menu = match_menu_with_ocr(menu, ocr_menus)

    return {
        "menu": menu,
        "attributes": attrs,
        "needs_recommendation": False,
        "matched_menu": matched_menu or menu,
        "confidence": 0.9 if matched_menu else 0.7
    }


# 테스트
if __name__ == "__main__":
    test_cases = [
        "아아 하나 줘",
        "차가운 라떼 주세요",
        "따뜻한 아메리카노",
        "달달한 커피 추천",
        "바닐라라떼 하나",
        "차가운 거 하나 줘",
        "커피 말고 시원한 거 하나 줘",
    ]

    ocr_sample = [
        "아이스 아메리카노",
        "핫 아메리카노",
        "카페라떼",
        "바닐라라떼"
    ]

    for t in test_cases:
        print(f"\n입력: {t}")
        print(extract_entity(t, ocr_sample))