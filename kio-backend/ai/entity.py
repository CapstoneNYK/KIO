import re
from typing import Dict, Optional
from ai.dictionary import MENU_KEYWORDS, ATTRIBUTE_KEYWORDS

QUANTITY_MAP = {
    "한": 1, "하나": 1,
    "두": 2, "둘": 2,
    "세": 3, "셋": 3,
    "네": 4, "넷": 4,
    "다섯": 5,
    "여섯": 6,
    "일곱": 7,
    "여덟": 8,
    "아홉": 9,
    "열": 10,
}


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    return text


def extract_quantity(text: str) -> int:
    # 숫자 + 단위 (예: "2잔", "3개")
    m = re.search(r"(\d+)\s*(?:잔|개|컵)", text)
    if m:
        return int(m.group(1))

    # 한글 수사 + 단위 (예: "두 잔", "세잔")
    for word, num in sorted(QUANTITY_MAP.items(), key=lambda x: -len(x[0])):
        pattern = word + r"\s*(?:잔|개|컵)?"
        if re.search(pattern, text):
            return num

    return 1


def extract_menu(text: str, ocr_menus: list = None) -> Optional[str]:
    text_norm = normalize_text(text)

    # 1단계: 축약어 → 정식 메뉴명으로 변환 ("아아" → "아메리카노")
    for key in sorted(MENU_KEYWORDS.keys(), key=len, reverse=True):
        if normalize_text(key) in text_norm:
            text_norm = text_norm.replace(normalize_text(key), normalize_text(MENU_KEYWORDS[key]))
            break

    # 2단계: OCR DB 메뉴와 직접 매칭 (가장 긴 매칭 우선)
    if ocr_menus:
        best_match, best_len = None, 0
        for ocr in ocr_menus:
            ocr_norm = normalize_text(ocr)
            if (ocr_norm in text_norm or text_norm in ocr_norm) and len(ocr_norm) > best_len:
                best_match, best_len = ocr, len(ocr_norm)
        if best_match:
            return best_match

    # 3단계: OCR 없으면 dictionary 결과 반환
    for key in sorted(MENU_KEYWORDS.keys(), key=len, reverse=True):
        if normalize_text(key) in normalize_text(text):
            return MENU_KEYWORDS[key]

    return None


def extract_attributes(text: str):
    text = normalize_text(text)
    attrs = []
    for key, value in ATTRIBUTE_KEYWORDS.items():
        if normalize_text(key) in text:
            attrs.append(value)
    return attrs


def extract_entity(text: str, ocr_menus: list = None) -> Dict:
    menu = extract_menu(text, ocr_menus)
    attrs = extract_attributes(text)
    quantity = extract_quantity(text)

    if not menu:
        return {
            "menu": None,
            "attributes": attrs,
            "quantity": quantity,
            "needs_recommendation": True,
            "matched_menu": None,
            "confidence": 0.0
        }

    # OCR에서 가져온 메뉴명엔 이미 온도가 포함될 수 있으므로 중복 방지
    menu_norm = normalize_text(menu)
    if "ice" in attrs and not any(w in menu_norm for w in ["아이스", "ice"]):
        menu = "아이스 " + menu
    elif "hot" in attrs and not any(w in menu_norm for w in ["핫", "따뜻한", "hot"]):
        menu = "핫 " + menu

    return {
        "menu": menu,
        "attributes": attrs,
        "quantity": quantity,
        "needs_recommendation": False,
        "matched_menu": menu,
        "confidence": 0.9 if ocr_menus else 0.7
    }


MULTI_SPLIT_PATTERN = re.compile(r'\s*(?:이랑|랑|하고|그리고|과|와)\s*')


def extract_multi_order(text: str, ocr_menus: list = None) -> list:
    parts = MULTI_SPLIT_PATTERN.split(text)
    results = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        entity = extract_entity(part, ocr_menus)
        if entity["menu"]:
            results.append(entity)

    if not results:
        return [extract_entity(text, ocr_menus)]
    return results
