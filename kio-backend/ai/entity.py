import re
from typing import Dict, Optional
from ai.dictionary import MENU_KEYWORDS, ATTRIBUTE_KEYWORDS

OPTION_KEYWORDS = {
    "샷추가": "샷추가",
    "샷 추가": "샷추가",
    "샷넣어": "샷추가",
    "샷 넣어": "샷추가",
    "더블샷": "샷추가",
    "샤추가": "샷추가",
    "셔츠가": "샷추가",
    "연하게": "연하게",
    "약하게": "연하게",
    "연하게해줘": "연하게",
}

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


def _unify_ae_e(ch: str) -> str:
    """한글 음절 하나를 받아 애/에(ㅐ/ㅔ), 얘/예(ㅒ/ㅖ) 모음 차이를 하나로 합친다.

    한국어는 ㅐ와 ㅔ 발음이 실제로 거의 구분되지 않아서, STT가 "카페라떼"를
    "카페라 때"처럼 다른 철자로 옮겨 적는 경우가 흔하다. 이 때문에 정확한
    철자로만 매칭하던 메뉴 사전이 오인식된 텍스트를 못 찾는 문제가 있었다.
    음절을 초성/중성/종성으로 분해해서 중성이 ㅐ/ㅒ면 각각 ㅔ/ㅖ로 바꾼 뒤
    다시 조합하면, "때"와 "떼" 같은 쌍이 정규화 후 동일한 문자가 되어
    메뉴 매칭이 발음 기준으로 관대해진다.
    """
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        offset = code - 0xAC00
        initial = offset // (21 * 28)
        medial = (offset % (21 * 28)) // 28
        final = offset % 28
        if medial == 1:      # ㅐ -> ㅔ
            medial = 5
        elif medial == 3:    # ㅒ -> ㅖ
            medial = 7
        return chr(0xAC00 + (initial * 21 + medial) * 28 + final)
    return ch


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    text = "".join(_unify_ae_e(ch) for ch in text)
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


def extract_options_from_text(text: str) -> list:
    text_norm = normalize_text(text)
    found = []
    for key, value in OPTION_KEYWORDS.items():
        if normalize_text(key) in text_norm and value not in found:
            found.append(value)
    return found


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
    options = extract_options_from_text(text)

    if not menu:
        return {
            "menu": None,
            "attributes": attrs,
            "quantity": quantity,
            "options": options,
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
        "options": options,
        "needs_recommendation": False,
        "matched_menu": menu,
        "confidence": 0.9 if ocr_menus else 0.7
    }


MULTI_SPLIT_PATTERN = re.compile(r'\s*(?:이랑|랑|하고|그리고|과|와|,|，)\s*')


def extract_all_menus_from_text(text: str, ocr_menus: list = None) -> list:
    """구분자 없이 나열된 텍스트에서 등장 순서대로 모든 메뉴 추출.
    축약어 치환을 먼저 하면 '바닐라라떼'→'바닐라카페라떼'처럼 깨지므로,
    풀 메뉴명으로 직접 매칭만 수행한다."""
    text_norm = normalize_text(text)

    # 후보: OCR 메뉴 + MENU_KEYWORDS 값(풀 메뉴명) + 키(축약어), 길이 내림차순
    candidates = []
    if ocr_menus:
        candidates += [(normalize_text(m), m) for m in ocr_menus]
    for v in set(MENU_KEYWORDS.values()):
        candidates.append((normalize_text(v), v))
    for k, v in MENU_KEYWORDS.items():
        norm_k = normalize_text(k)
        norm_v = normalize_text(v)
        if norm_k != norm_v:
            candidates.append((norm_k, v))

    seen = set()
    unique = []
    for norm, original in sorted(candidates, key=lambda x: -len(x[0])):
        if norm not in seen:
            seen.add(norm)
            unique.append((norm, original))

    found = []
    remaining = text_norm
    while remaining:
        best_pos = len(remaining)
        best = None
        for norm, original in unique:
            pos = remaining.find(norm)
            if 0 <= pos < best_pos:
                best_pos = pos
                best = (norm, original)
            elif best and 0 <= pos == best_pos and len(norm) > len(best[0]):
                best = (norm, original)  # 같은 위치면 긴 것 우선
        if best is None:
            break
        norm, original = best

        # 메뉴 이후 ~ 다음 메뉴 시작 전 구간에서 수량·옵션 추출
        after_menu = remaining[best_pos + len(norm):]
        next_menu_pos = len(after_menu)
        for n2, _ in unique:
            p = after_menu.find(n2)
            if 0 <= p < next_menu_pos:
                next_menu_pos = p
        qty_segment = after_menu[:next_menu_pos]
        qty = extract_quantity(qty_segment) if qty_segment else 1
        options = extract_options_from_text(qty_segment) if qty_segment else []

        found.append((original, qty, options))
        remaining = remaining[:best_pos] + remaining[best_pos + len(norm):]

    return found


def extract_multi_order(text: str, ocr_menus: list = None) -> list:
    # 1단계: 구분자로 분리 시도
    parts = MULTI_SPLIT_PATTERN.split(text)
    if len(parts) > 1:
        results = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            entity = extract_entity(part, ocr_menus)
            if entity["menu"]:
                results.append(entity)
        if results:
            return results

    # 2단계: 구분자 없이 나열된 경우 전체 텍스트 스캔
    menu_qty_pairs = extract_all_menus_from_text(text, ocr_menus)
    if len(menu_qty_pairs) > 1:
        attrs = extract_attributes(text)
        results = []
        for menu, qty, options in menu_qty_pairs:
            results.append({
                "menu": menu,
                "attributes": attrs,
                "quantity": qty,
                "options": options,
                "needs_recommendation": False,
                "matched_menu": menu,
                "confidence": 0.7,
            })
        return results

    return [extract_entity(text, ocr_menus)]
