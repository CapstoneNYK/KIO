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

# 추천 목록에서 "1번/첫번째로 담아줘"처럼 순서로 메뉴를 고르는 발화를 해석하기 위한 매핑.
# recommend 응답으로 받은 메뉴 리스트의 인덱스(1부터 시작)를 가리킨다.
ORDINAL_KEYWORDS: dict[str, int] = {
    "첫번째": 1, "첫 번째": 1, "1번째": 1, "1번": 1, "일번": 1,
    "두번째": 2, "두 번째": 2, "2번째": 2, "2번": 2,
    "세번째": 3, "세 번째": 3, "3번째": 3, "3번": 3,
    "네번째": 4, "네 번째": 4, "4번째": 4, "4번": 4,
    "다섯번째": 5, "다섯 번째": 5, "5번째": 5, "5번": 5,
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


# STT가 "디카페인"을 자주 잘못 받아 적는 변형들 (티카페인, 디카패인, 디 카페인 ...)
_STT_DECAF = re.compile(r"디\s*카\s*[페패]\s*인|티카\s*[페패]\s*인")


# "샷 추가"를 "찹 추가/샵 추가/삿 추가"로 잘못 받아 적는 경우 ("추가" 바로 앞일 때만 보정해 오탐을 막는다)
_STT_SHOT = re.compile(r"(?:찹|챱|샵|삿|셧|샤)(?=\s*(?:을|를)?\s*(?:더\s*)?추가)")


# 영어 알파벳 T로 적힌 "티"("T로 된 거"), "할인에 등/할인 해택" 같은 오인식
_STT_TEA_T = re.compile(r"(?<![A-Za-z])[Tt](?![A-Za-z])(?=\s*(?:로|가|를|는|은|종류|류|말고|계열|\b))")
_STT_DISCOUNT = re.compile(r"할인\s*(?:에\s*등|해택|헤택|혜택|에\s*택)")


def fix_stt_errors(text: str) -> str:
    """음성 인식(STT)이 자주 틀리는 단어를 바로잡는다. 메뉴 추출 전에 한 번 적용."""
    text = _STT_DECAF.sub("디카페인", text)
    text = _STT_TEA_T.sub("티", text)
    text = _STT_DISCOUNT.sub("할인혜택", text)
    return _STT_SHOT.sub("샷", text)


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    text = "".join(_unify_ae_e(ch) for ch in text)
    return text


# "샷 두 번 추가", "2샷 추가"의 숫자는 메뉴 수량이 아니라 옵션(샷) 개수다
_SHOT_NUM_STRIP = re.compile(r"(?:샷|샤)\s*(?:\d+|한|하나|두|둘|세|셋|네|넷|다섯)\s*(?:개|번|잔|샷|게)?|(?:\d+|한|하나|두|둘|세|셋|네|넷|다섯)\s*(?:샷|샤)")


def extract_quantity(text: str) -> int:
    text = _SHOT_NUM_STRIP.sub(" ", text)
    # 숫자 + 단위 (예: "2잔", "3개")
    m = re.search(r"(\d+)\s*(?:잔|개|게|컵)", text)
    if m:
        return int(m.group(1))

    # 한글 수사 + 단위 (예: "두 잔", "세잔")
    for word, num in sorted(QUANTITY_MAP.items(), key=lambda x: -len(x[0])):
        # 단위가 붙은 경우("세 잔")는 그대로 인정하고, 단위가 없으면 독립된 단어일 때만 인정한다
        # ("주세요"의 '세', "한잔 해요"가 아닌 "하나 주세요" 등 오탐 방지)
        pattern = word + r"\s*(?:잔|개|게|컵)|(?<![가-힣])" + word + r"(?![가-힣])"
        if re.search(pattern, text):
            return num

    return 1


def extract_ordinal(text: str) -> Optional[int]:
    """"1번으로 담아줘", "두번째로 줘" 같은 순서 참조 표현에서 순번을 추출한다.
    직전에 추천받은 메뉴 목록 중 몇 번째를 고르려는 건지 알아낼 때 쓴다."""
    text_norm = normalize_text(text)
    for key in sorted(ORDINAL_KEYWORDS.keys(), key=len, reverse=True):
        if normalize_text(key) in text_norm:
            return ORDINAL_KEYWORDS[key]
    return None


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


def _menu_by_split_tokens(text_norm: str, menu_names: list) -> Optional[str]:
    """"에이드 중에 레몬으로", "스무디는 딸기로"처럼 메뉴명의 첫·끝 단어가 떨어져 나온 발화를 매칭한다.
    후보가 정확히 하나일 때만 인정한다(애매하면 None)."""
    cands = []
    for name in menu_names:
        toks = name.split()
        if len(toks) < 2:
            continue
        first, last = normalize_text(toks[0]), normalize_text(toks[-1])
        if first in text_norm and last in text_norm:
            cands.append(name)
    return cands[0] if len(cands) == 1 else None


def extract_menu(text: str, menu_names: list = None) -> Optional[str]:
    keywords = active_keywords(menu_names)
    text_norm = normalize_text(text)

    # 1단계: 관리자 메뉴명 직접 매칭 (가장 긴 매칭 우선).
    # 축약어보다 먼저 봐야 '헤이즐넛라떼'가 '라떼' → '카페라떼'로 잘못 치환되지 않는다.
    if menu_names:
        match = _longest_menu_in_text(text_norm, menu_names)
        if match:
            return match

    if menu_names:
        match = _menu_by_split_tokens(text_norm, menu_names)
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


# ── 옵션 구조화 (샷 개수 / 시럽·크림 양 / 사이즈 / 포장) ─────────────────────────
# 단순 키워드("샷추가")만 잡던 방식에서 나아가, "샷 두 번 추가", "시럽은 조금만",
# "크림은 절반만", "작은 사이즈로" 같은 표현을 {kind, name, count}로 구조화한다.
# 패턴은 normalize_text 기준(공백 제거, ㅐ→ㅔ 통일)으로 컴파일한다.

def _rx(pattern: str) -> "re.Pattern":
    return re.compile(normalize_text(pattern))


_NUM_WORDS = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4, "다섯": 5}
_NUM = r"(\d+|한|하나|두|둘|세|셋|네|넷|다섯)"

_SHOT_COUNT_RES = [
    _rx(r"(?:샷|샤|셔츠)(?:을|를|은)?" + _NUM + r"(?:개|번|잔|샷)?(?:만)?(?:더)?(?:추가|넣|더)"),
    _rx(_NUM + r"(?:샷|샤)(?:만)?(?:더)?(?:추가|넣|더)"),
]
_SHOT_PLAIN_RE = _rx(r"(?:샷|샤|셔츠)(?:을|를)?(?:더)?(?:추가|넣|더)|추가샷")
# 더블샷 = 기본 1샷 + 추가 1샷, 트리플샷 = 추가 2샷 (기존 "더블샷 → 샷추가" 동작과 일치)
_SHOT_MULTI = {"더블샷": 1, "트리플샷": 2}

_LEVEL_NONE = _rx(r"빼|없이|넣지|제외|말고|안넣|안줘|안주")
_LEVEL_HALF = _rx(r"절반|반만|반정도|1/2|하프")
_LEVEL_LESS = _rx(r"조금|적게|살짝|약간|덜|소량")
_LEVEL_MORE = _rx(r"많이|듬뿍|넉넉|가득")

_SYRUP_WORDS = ("시럽",)
_CREAM_WORDS = ("크림", "휘핑")

_SIZE_PATTERNS = [
    ("S", _rx(r"작은|작게|스몰|small|숏")),
    ("L", _rx(r"큰사이즈|큰거|큰걸|큰것|큰|크게|라지|large|벤티")),
    ("M", _rx(r"보통사이즈|중간사이즈|미디엄|레귤러|medium|톨")),
]
_SIZE_WORD_RE = _rx(r"사이즈|크기")

_PACK_RE = _rx(r"포장|테이크아웃|가져갈|가져가|들고갈|싸줘|싸서|싸주|싸드|싸가")
_DINE_RE = _rx(r"매장|먹고갈|먹고가|드시고|여기서")


def _level_of(segment: str) -> str:
    """시럽/크림 구간 텍스트에서 양 표현을 추출한다. 우선순위: 절반 > 없음 > 적게 > 많이."""
    if _LEVEL_HALF.search(segment):
        return "절반"
    if _LEVEL_NONE.search(segment):
        return "없음"
    if _LEVEL_LESS.search(segment):
        return "적게"
    if _LEVEL_MORE.search(segment):
        return "많이"
    return "추가"


def extract_option_details(text: str) -> list:
    """발화에서 옵션을 구조화해 돌려준다.
    각 항목: {"kind": shot|light|syrup|cream|size, "name": 표시 이름, "count": 수량(샷 개수 등)}"""
    text_norm = normalize_text(text)
    details = []

    # 샷: "샷 두 번 추가", "2샷 추가", "더블샷", "샷 추가"
    shot_count = None
    for word, n in _SHOT_MULTI.items():
        if normalize_text(word) in text_norm:
            shot_count = n
    if shot_count is None:
        for rx in _SHOT_COUNT_RES:
            m = rx.search(text_norm)
            if m:
                g = m.group(1)
                shot_count = int(g) if g.isdigit() else _NUM_WORDS.get(g, 1)
                break
    if shot_count is None and _SHOT_PLAIN_RE.search(text_norm):
        shot_count = 1
    if shot_count is not None and shot_count >= 1:
        details.append({"kind": "shot", "name": "샷추가", "count": shot_count})

    # 연하게 (기존 키워드 유지)
    for key in ("연하게", "약하게"):
        if normalize_text(key) in text_norm:
            details.append({"kind": "light", "name": "연하게", "count": 1})
            break

    # 시럽/크림: 해당 단어부터 다음 시럽/크림 단어 직전까지를 그 옵션의 구간으로 본다
    # (예: "크림은 기본의 절반만 넣고 시럽은 조금만 넣어 줘" → 크림=절반, 시럽=적게)
    markers = []
    for word in _SYRUP_WORDS:
        for m in re.finditer(normalize_text(word), text_norm):
            markers.append((m.start(), "syrup", "시럽"))
    for word in _CREAM_WORDS:
        for m in re.finditer(normalize_text(word), text_norm):
            markers.append((m.start(), "cream", "크림"))
    markers.sort()
    for i, (pos, kind, label) in enumerate(markers):
        if any(d["kind"] == kind for d in details):
            continue
        # 같은 종류 단어(예: "크림 휘핑")가 붙어 있으면 한 구간으로 묶는다
        end = len(text_norm)
        for next_pos, next_kind, _ in markers[i + 1:]:
            if next_kind != kind:
                end = next_pos
                break
        level = _level_of(text_norm[pos:end])
        details.append({"kind": kind, "name": f"{label} {level}", "count": 1})

    # 사이즈
    if _SIZE_WORD_RE.search(text_norm) or any(rx.search(text_norm) for _, rx in _SIZE_PATTERNS[:2]):
        for size, rx in _SIZE_PATTERNS:
            if rx.search(text_norm):
                details.append({"kind": "size", "name": f"사이즈 {size}", "count": 1})
                break

    return details


def extract_packaging(text: str) -> Optional[bool]:
    """포장이면 True, 매장 식사면 False, 언급 없으면 None."""
    text_norm = normalize_text(text)
    if _PACK_RE.search(text_norm):
        return True
    if _DINE_RE.search(text_norm):
        return False
    return None


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
    option_details = extract_option_details(text)
    packaging = extract_packaging(text)

    if not menu:
        return {
            "menu": None,
            "attributes": attrs,
            "quantity": quantity,
            "options": options,
            "option_details": option_details,
            "packaging": packaging,
            "needs_recommendation": True,
            "matched_menu": None,
            "confidence": 0.0
        }

    # "디카페인으로"처럼 디카페인 지정이 있고 해당 메뉴의 디카페인 버전이 존재하면 그쪽으로 치환
    if menu_names and "디카페인" in text.replace(" ", "") and not menu.startswith("디카페인"):
        decaf_name = f"디카페인 {menu}"
        for name in menu_names:
            if normalize_text(name) == normalize_text(decaf_name):
                menu = name
                break

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
        "option_details": option_details,
        "packaging": packaging,
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
        details = extract_option_details(qty_segment) if qty_segment else []

        found.append((original, qty, options, details))
        remaining = remaining[:best_pos] + remaining[best_pos + len(norm):]

    return found


_DISTRIBUTIVE = re.compile(normalize_text(r"씩|둘다|모두|전부|다같이"))


def _share_trailing_temperature(results: list, last_part: str) -> None:
    """"얼그레이랑 캐모마일 따뜻하게 하나씩"처럼 마지막에 온 온도·'씩' 표현은 앞 메뉴에도 적용한다."""
    if len(results) < 2 or not _DISTRIBUTIVE.search(normalize_text(last_part)):
        return
    last = results[-1]
    temp = "hot" if "hot" in last["attributes"] else "ice" if "ice" in last["attributes"] else None
    if not temp:
        return
    prefix = "핫 " if temp == "hot" else "아이스 "
    for prev in results[:-1]:
        if "hot" in prev["attributes"] or "ice" in prev["attributes"]:
            continue
        prev["attributes"] = list(prev["attributes"]) + [temp]
        if prev["menu"] and not prev["menu"].startswith(("핫 ", "아이스 ")):
            prev["menu"] = prefix + prev["menu"]


# "라떼 세 잔, 하나는 샷 추가하고 하나는 시럽 추가" — 같은 메뉴를 잔마다 다른 옵션으로 나눠 주문
_UNIT_START = re.compile(r"(?<![가-힣0-9])(\d+|한|하나|두|둘|세|셋|네|넷)\s*(?:잔|개)?\s*(?:은|는|만)(?=\s)")
_UNIT_NUM = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4}


def _per_unit_orders(text: str, menu_names: Optional[list]) -> Optional[list]:
    starts = list(_UNIT_START.finditer(text))
    if not starts:
        return None
    prefix = text[:starts[0].start()]
    base = extract_entity(prefix, menu_names)
    if not base["menu"]:
        return None
    total = extract_quantity(prefix)
    packaging = extract_packaging(text)
    out, used = [], 0
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        seg = text[m.end():end]
        g = m.group(1)
        n = int(g) if g.isdigit() else _UNIT_NUM.get(g, 1)
        details = extract_option_details(seg)
        e = dict(base)
        e.update(quantity=n, option_details=details, options=[d["name"] for d in details], packaging=packaging)
        out.append(e)
        used += n
    rest = max(total - used, 0)
    if rest:
        e = dict(base)
        e.update(quantity=rest, packaging=packaging)
        out.append(e)
    return out


def extract_multi_order(text: str, menu_names: list = None) -> list:
    text = fix_stt_errors(text)
    per_unit = _per_unit_orders(text, menu_names)
    if per_unit:
        return per_unit
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
            elif results:
                # "샷 추가하고 시럽은 조금만 해서 포장해 줘"처럼 '하고/랑'으로 끊겼지만 메뉴가 없는 조각은
                # 새 주문이 아니라 직전 메뉴의 옵션/포장 요청이다. 버리지 않고 직전 메뉴에 합친다.
                prev = results[-1]
                have = {d["kind"] for d in prev["option_details"]}
                for d in entity["option_details"]:
                    if d["kind"] not in have:
                        prev["option_details"].append(d)
                        have.add(d["kind"])
                for name in entity["options"]:
                    if name not in prev["options"]:
                        prev["options"].append(name)
                if prev.get("packaging") is None and entity.get("packaging") is not None:
                    prev["packaging"] = entity["packaging"]
        if results:
            _share_trailing_temperature(results, parts[-1])
            return results

    # 2단계: 구분자 없이 나열된 경우 전체 텍스트 스캔
    menu_qty_pairs = extract_all_menus_from_text(text, menu_names)
    if len(menu_qty_pairs) > 1:
        attrs = extract_attributes(text)
        results = []
        packaging = extract_packaging(text)
        for menu, qty, options, details in menu_qty_pairs:
            results.append({
                "menu": menu,
                "attributes": attrs,
                "quantity": qty,
                "options": options,
                "option_details": details,
                "packaging": packaging,
                "needs_recommendation": False,
                "matched_menu": menu,
                "confidence": 0.7,
            })
        return results

    return [extract_entity(text, menu_names)]
