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


def active_keywords(menu_names: Optional[list]) -> dict[str, str]:
    """축약어 사전 중 실제로 존재하는 메뉴를 가리키는 항목만 남긴다 (삭제/이름 변경된 메뉴 제외).
    사전 값은 관리자 메뉴의 실제 표기로 바꿔 돌려준다. menu_names가 None이면 필터링하지 않는다."""
    if menu_names is None:
        return MENU_KEYWORDS
    by_norm = {normalize_text(m): m for m in menu_names}
    return {k: by_norm[normalize_text(v)] for k, v in MENU_KEYWORDS.items() if normalize_text(v) in by_norm}


def _longest_menu_in_text(text_norm: str, menu_names: list) -> Optional[str]:
    best_match, best_len = None, 0
    for name in menu_names:
        name_norm = normalize_text(name)
        if name_norm and name_norm in text_norm and len(name_norm) > best_len:
            best_match, best_len = name, len(name_norm)
    return best_match


def _longest_menu_containing_text(text_norm: str, menu_names: list) -> Optional[str]:
    best_match, best_len = None, 0
    for name in menu_names:
        name_norm = normalize_text(name)
        if text_norm in name_norm and len(name_norm) > best_len:
            best_match, best_len = name, len(name_norm)
    return best_match


def extract_menu(text: str, menu_names: list = None) -> Optional[str]:
    keywords = active_keywords(menu_names)
    text_norm = normalize_text(text)

    # 1단계: 관리자 메뉴명 직접 매칭 (가장 긴 매칭 우선).
    # 축약어보다 먼저 봐야 '헤이즐넛라떼'가 '라떼' → '카페라떼'로 잘못 치환되지 않는다.
    if menu_names:
        match = _longest_menu_in_text(text_norm, menu_names)
        if match:
            return match

    # 2단계: 축약어 → 정식 메뉴명 ("아아" → "아메리카노")
    for key in sorted(keywords.keys(), key=len, reverse=True):
        if normalize_text(key) in text_norm:
            return keywords[key]

    # 3단계: 발화 전체가 메뉴명의 일부인 경우 ("바닐라" → "바닐라라떼")
    if menu_names:
        return _longest_menu_containing_text(text_norm, menu_names)

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


def extract_entity(text: str, menu_names: list = None) -> Dict:
    menu = extract_menu(text, menu_names)
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

    # 메뉴명에 이미 온도가 포함돼 있으면 중복해서 붙이지 않는다
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
        "confidence": 0.9 if menu_names else 0.7
    }


MULTI_SPLIT_PATTERN = re.compile(r'\s*(?:이랑|랑|하고|그리고|과|와|,|，)\s*')


def extract_all_menus_from_text(text: str, menu_names: list = None) -> list:
    """구분자 없이 나열된 텍스트에서 등장 순서대로 모든 메뉴 추출.
    축약어 치환을 먼저 하면 '바닐라라떼'→'바닐라카페라떼'처럼 깨지므로,
    풀 메뉴명으로 직접 매칭만 수행한다."""
    text_norm = normalize_text(text)
    keywords = active_keywords(menu_names)

    # 후보: 관리자 메뉴 + 축약어 사전 값(풀 메뉴명) + 키(축약어), 길이 내림차순
    candidates = []
    if menu_names:
        candidates += [(normalize_text(m), m) for m in menu_names]
    for v in set(keywords.values()):
        candidates.append((normalize_text(v), v))
    for k, v in keywords.items():
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


def extract_multi_order(text: str, menu_names: list = None) -> list:
    # 1단계: 구분자로 분리 시도
    parts = MULTI_SPLIT_PATTERN.split(text)
    if len(parts) > 1:
        results = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            entity = extract_entity(part, menu_names)
            if entity["menu"]:
                results.append(entity)
        if results:
            return results

    # 2단계: 구분자 없이 나열된 경우 전체 텍스트 스캔
    menu_qty_pairs = extract_all_menus_from_text(text, menu_names)
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

    return [extract_entity(text, menu_names)]
