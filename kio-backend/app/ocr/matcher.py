import csv
import re
import difflib
from pathlib import Path

_DATA_PATH = Path(__file__).parent.parent / "data" / "cafe_menu_processed.csv"

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

def _load_menu_data():
    menu_names, categories, records = [], set(), []
    if not _DATA_PATH.exists():
        return menu_names, list(categories), records
    with open(_DATA_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("name", "").strip()
            category = row.get("category", "").strip()
            if name:
                menu_names.append(name)
            if category:
                categories.add(category)
            records.append(row)
    return menu_names, list(categories), records

_MENU_NAMES, _CATEGORIES, _RECORDS = _load_menu_data()
_CATEGORY_SET = {c.lower() for c in _CATEGORIES}

def _fuzzy_match_menu(text: str, threshold: float = 0.75):
    best_score, best_name = 0.0, None
    for name in _MENU_NAMES:
        score = difflib.SequenceMatcher(None, text, name).ratio()
        if score > best_score:
            best_score = score
            best_name = name
    if best_score >= threshold and best_name:
        for record in _RECORDS:
            if record.get("name", "").strip() == best_name:
                return {"matched_name": best_name, "score": round(best_score, 3), **record}
    return None

def _classify_text(text: str) -> dict:
    stripped = text.strip()
    for keyword, subtype in _ACTION_KEYWORDS.items():
        if keyword in stripped:
            return {"label": "action_button", "subtype": subtype}
    if _PRICE_PATTERN.match(stripped.replace(" ", "")):
        return {"label": "price"}
    if stripped.lower() in _CATEGORY_SET:
        return {"label": "category", "category": stripped}
    for cat in _CATEGORIES:
        score = difflib.SequenceMatcher(None, stripped, cat).ratio()
        if score >= 0.85:
            return {"label": "category", "category": cat, "score": round(score, 3)}
    menu_match = _fuzzy_match_menu(stripped)
    if menu_match:
        return {"label": "menu_item", **menu_match}
    return {"label": "unknown"}

def classify_ocr_results(ocr_items: list[dict]) -> list[dict]:
    return [{**item, **_classify_text(item["text"])} for item in ocr_items]
