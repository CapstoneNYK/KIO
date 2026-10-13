"""맞춤형 추천: 발화에서 취향/조건을 추출하고, 실제 메뉴 DB를 규칙으로 필터링해 추천한다.

설계 의도
- "산미 있는 따뜻한 커피", "카페인 없는 시원한 거 3개만"처럼 조건이 명확한 요청은
  LLM에 맡기지 않고 규칙으로 필터링한다 -> 조건과 실제 메뉴 속성이 항상 일치하고(환각 없음),
  품절 메뉴가 섞이지 않으며, 결과가 매번 같다.
- 조건이 하나도 안 잡히는 막연한 요청("뭐 마실까?")만 기존 LLM 추천으로 넘긴다.
- 조건을 모두 만족하는 메뉴가 없으면 뒤쪽 조건부터 하나씩 완화해 대안을 제시하고,
  어떤 조건을 뺐는지 사용자에게 알려준다.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from ai.entity import normalize_text


def _rx(pattern: str) -> "re.Pattern":
    return re.compile(normalize_text(pattern))


# 맛 태그: (패턴, 태그). 메뉴 DB의 tags 값과 같은 이름을 쓴다.
_TAG_PATTERNS = [
    (_rx(r"산미|신맛"), "산미"),
    (_rx(r"상큼|새콤|시큼|상콤"), "상큼"),
    (_rx(r"달달|달콤|단맛|단거|단음료|당충전|당떨어"), "달콤"),
    (_rx(r"고소|구수"), "고소"),
    (_rx(r"쌉쌀|쌉싸|쓴맛|씁쓸"), "쌉쌀"),
    (_rx(r"진한|찐한|진하|찐하"), "진한"),
    (_rx(r"부드럽|부드러|순한|크리미"), "부드러운"),
    (_rx(r"향긋|향기|허브"), "향긋"),
    (_rx(r"과일|프루티|과즙"), "과일"),
    (_rx(r"탄산|톡쏘"), "탄산"),
    (_rx(r"깔끔|깨끗|담백"), "깔끔"),
    (_rx(r"상쾌|개운"), "상쾌"),
]

# 부정 표현: 해당 맛을 "제외"한다 ("안 단 거", "덜 달달한", "달지 않은")
_NEGATED_TAGS = [
    (_rx(r"안달|덜달|달지않|달지는않|안단|덜단|단거말고|안쓴|안쓰|쓰지않"), "달콤"),
    (_rx(r"안쓴|쓰지않|안쌉|덜쓴|덜쌉"), "쌉쌀"),
    (_rx(r"안시|시지않|안새콤|안상큼"), "상큼"),
]

_RE_HOT = _rx(r"따뜻|뜨거|뜨겁|핫|hot|뜨아|뜨라")
_RE_ICE = _rx(r"차가|차갑|시원|아이스|ice|얼음|아아|아라|냉")

_RE_NO_CAFFEINE = _rx(r"카페인(?:이|은|을|도)?(?:없|빼|안|적|낮|약|프리)|디카페인|잠못자|잠이안")
_RE_CAFFEINE = _rx(r"카페인(?:이|은|을)?(?:있|충전|많|듬뿍)|잠깨|졸려|졸리|졸린|졸음|각성|피곤")

_CATEGORY_PATTERNS = [
    (_rx(r"스무디"), ["스무디"]),
    (_rx(r"에이드"), ["에이드"]),
    (_rx(r"주스"), ["주스"]),
    (_rx(r"티(?!켓)|(?<!아|따|시|차)차(?!가|갑|분)|허브티"), ["티"]),
]
_RE_COFFEE = _rx(r"커피|라떼|아메리카노")
_RE_NOT_COFFEE = _rx(r"커피말고|커피빼고|커피는빼|논커피|커피말구|커피안|커피제외|커피아닌")
_COFFEE_CATEGORIES = ["커피", "디카페인"]

_RE_CHEAP = _rx(r"저렴|싼거|싸게|싼음료|가성비|제일싼|가장싼")
_RE_PRICE_DIGIT = _rx(r"(\d+(?:,\d{3})*)(천|만)?원?(?:이하|미만|아래|밑|이내|까지|안쪽|보다싼|보다저렴)")
_KO_DIGIT = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_RE_PRICE_KO = _rx(r"([일이삼사오육칠팔구])(천|만)원?(?:이하|미만|아래|밑|이내|까지|안쪽)")

_NUM_WORDS = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4, "다섯": 5}
_RE_LIMIT = _rx(r"(\d+|한|하나|두|둘|세|셋|네|넷|다섯)(?:(?:개|가지|종류|잔)(?:만|정도|씩)?|만)")

MAX_LIMIT = 5
DEFAULT_LIMIT = 3


@dataclass
class Conditions:
    temperature: Optional[str] = None          # "HOT" | "ICE"
    caffeine: Optional[bool] = None            # False=카페인 없는 것만, True=카페인 있는 것만
    tags: list = field(default_factory=list)   # 반드시 포함할 맛 태그
    exclude_tags: list = field(default_factory=list)
    categories: list = field(default_factory=list)          # 이 카테고리만
    exclude_categories: list = field(default_factory=list)  # 이 카테고리 제외
    max_price: Optional[int] = None
    cheap: bool = False
    limit: Optional[int] = None

    def is_empty(self) -> bool:
        """추천 '조건'이 하나라도 있는지. (개수 지정만 있는 경우는 조건 없음으로 본다.)"""
        return not (
            self.temperature or self.caffeine is not None or self.tags or self.exclude_tags
            or self.categories or self.exclude_categories or self.max_price or self.cheap
        )

    def describe(self, tags: Optional[list] = None) -> str:
        """조건을 자연스러운 명사구로 만든다. 예: "산미 있는 따뜻한 커피", "커피 말고 상큼한 메뉴"."""
        parts = []
        if self.exclude_categories and set(self.exclude_categories) >= set(_COFFEE_CATEGORIES):
            parts.append("커피 말고")
        if self.max_price:
            parts.append(f"{self.max_price:,}원 이하")
        elif self.cheap:
            parts.append("저렴한")
        if self.caffeine is False:
            parts.append("카페인 없는")
        elif self.caffeine is True:
            parts.append("카페인 있는")
        for t in (self.tags if tags is None else tags):
            parts.append(_TAG_ADJ.get(t, t))
        for t in self.exclude_tags:
            parts.append(_TAG_EXCLUDE_ADJ.get(t, f"{t} 적은"))
        if self.temperature == "HOT":
            parts.append("따뜻한")
        elif self.temperature == "ICE":
            parts.append("시원한")
        if self.categories:
            noun = "커피" if set(self.categories) == set(_COFFEE_CATEGORIES) else "/".join(self.categories)
        else:
            noun = "메뉴"
        return " ".join(parts + [noun])


_TAG_ADJ = {
    "산미": "산미 있는", "상큼": "상큼한", "달콤": "달콤한", "고소": "고소한", "쌉쌀": "쌉쌀한",
    "진한": "진한", "부드러운": "부드러운", "향긋": "향긋한", "과일": "과일 맛", "탄산": "탄산이 있는",
    "깔끔": "깔끔한", "상쾌": "상쾌한",
}
_TAG_EXCLUDE_ADJ = {"달콤": "달지 않은", "쌉쌀": "쓰지 않은", "상큼": "시지 않은"}


def _parse_price(text_norm: str) -> Optional[int]:
    m = _RE_PRICE_DIGIT.search(text_norm)
    if m:
        value = int(m.group(1).replace(",", ""))
        unit = m.group(2)
        if unit == "천":
            value *= 1000
        elif unit == "만":
            value *= 10000
        elif value < 100:          # "5원 이하" 같은 단위 누락은 천 원 단위로 해석하지 않고 무시
            return None
        return value
    m = _RE_PRICE_KO.search(text_norm)
    if m:
        value = _KO_DIGIT[m.group(1)]
        return value * (1000 if m.group(2) == "천" else 10000)
    return None


def parse_conditions(text: str) -> Conditions:
    t = normalize_text(text)
    c = Conditions()

    # 온도: 둘 다 말했으면 어느 쪽도 고르지 않는다
    hot, ice = bool(_RE_HOT.search(t)), bool(_RE_ICE.search(t))
    if hot and not ice:
        c.temperature = "HOT"
    elif ice and not hot:
        c.temperature = "ICE"

    # 카페인
    if _RE_NO_CAFFEINE.search(t):
        c.caffeine = False
    elif _RE_CAFFEINE.search(t):
        c.caffeine = True

    # 카테고리
    if _RE_NOT_COFFEE.search(t):
        c.exclude_categories = list(_COFFEE_CATEGORIES)
    for rx, cats in _CATEGORY_PATTERNS:
        if rx.search(t):
            c.categories.extend(cats)
    if not c.exclude_categories and not c.categories and _RE_COFFEE.search(t):
        # 디카페인 요청이면 디카페인 메뉴도 커피 범주에 포함 (카페인 조건이 따로 걸러준다)
        c.categories = list(_COFFEE_CATEGORIES)

    # 맛: 부정 표현을 먼저 처리하고 해당 구간은 긍정 매칭에서 제외
    scrubbed = t
    for rx, tag in _NEGATED_TAGS:
        if rx.search(scrubbed):
            if tag not in c.exclude_tags:
                c.exclude_tags.append(tag)
            scrubbed = rx.sub("", scrubbed)
    for rx, tag in _TAG_PATTERNS:
        if rx.search(scrubbed) and tag not in c.tags and tag not in c.exclude_tags:
            c.tags.append(tag)

    # 가격 / 저렴
    c.max_price = _parse_price(t)
    c.cheap = bool(_RE_CHEAP.search(t))

    # 개수
    m = _RE_LIMIT.search(t)
    if m:
        g = m.group(1)
        n = int(g) if g.isdigit() else _NUM_WORDS.get(g, DEFAULT_LIMIT)
        c.limit = max(1, min(n, MAX_LIMIT))
    return c


# ── 필터링 ───────────────────────────────────────────────────────────────────

def _matches(menu: dict, c: Conditions, tags: list) -> bool:
    if menu.get("sold_out"):
        return False
    if c.temperature and c.temperature not in menu.get("temps", []):
        return False
    if c.caffeine is False and menu.get("caffeine", True):
        return False
    if c.caffeine is True and not menu.get("caffeine", True):
        return False
    if c.categories and menu["category"] not in c.categories:
        return False
    if menu["category"] in c.exclude_categories:
        return False
    menu_tags = set(menu.get("tags", []))
    if any(t not in menu_tags for t in tags):
        return False
    if any(t in menu_tags for t in c.exclude_tags):
        return False
    if c.max_price and menu["price"] > c.max_price:
        return False
    return True


def _rank(menus: list, c: Conditions) -> list:
    if c.cheap:
        return sorted(menus, key=lambda m: (m["price"], m["id"]))
    return sorted(menus, key=lambda m: m["id"])


@dataclass
class Recommendation:
    answer: str
    menus: list            # 추천 메뉴명 (온도 조건이 있으면 "핫 아메리카노"처럼 접두어 포함)
    relaxed: list = field(default_factory=list)   # 완화(제외)한 조건 설명
    found: bool = True


def _display_name(menu: dict, c: Conditions) -> str:
    if c.temperature == "HOT":
        return f"핫 {menu['name']}"
    if c.temperature == "ICE" and "HOT" in menu.get("temps", []):
        return f"아이스 {menu['name']}"
    return menu["name"]


def recommend_by_conditions(text: str, menus: list) -> Optional[Recommendation]:
    """조건 기반 추천. 추출된 조건이 없으면 None(= LLM 추천으로 넘김)."""
    c = parse_conditions(text)
    if c.is_empty():
        return None

    limit = c.limit or DEFAULT_LIMIT
    required = list(c.tags)
    relaxed = []

    # 맛 조건은 뒤에서부터 하나씩 완화해 가며 결과를 찾는다
    while True:
        matched = [m for m in menus if _matches(m, c, required)]
        if matched or not required:
            break
        relaxed.append(required.pop())

    if not matched:
        return Recommendation(
            answer="죄송해요, 말씀하신 조건에 맞는 주문 가능한 메뉴를 찾지 못했어요. "
                   "온도나 종류를 바꿔서 다시 말씀해 주시겠어요?",
            menus=[], found=False,
        )

    picked = _rank(matched, c)
    # 맛 태그가 여러 개일 때는 더 많이 일치하는 메뉴를 앞으로
    if required and not c.cheap:
        picked.sort(key=lambda m: (-len(set(required) & set(m.get("tags", []))), m["id"]))
    picked = picked[:limit]

    lines = []
    for i, m in enumerate(picked, 1):
        tags = "·".join(m.get("tags", [])[:3])
        lines.append(f"{i}. {_display_name(m, c)} ({m['price']:,}원)" + (f" - {tags}" if tags else ""))

    head = f"{c.describe(required)}로 골라봤어요."
    if relaxed:
        head = (f"'{'·'.join(reversed(relaxed))}' 조건까지 모두 맞는 메뉴는 없어서, "
                f"그 조건을 빼고 {c.describe(required)}로 골라봤어요.")
    answer = head + "\n" + "\n".join(lines) + "\n원하는 번호를 말씀해 주세요."
    return Recommendation(
        answer=answer,
        menus=[_display_name(m, c) for m in picked],
        relaxed=list(reversed(relaxed)),
    )


# ── 품절 대체 메뉴 ───────────────────────────────────────────────────────────

def find_alternatives(sold_out_name: str, menus: list, limit: int = 2) -> list:
    """품절 메뉴와 같은 카테고리(없으면 같은 카페인 유형)에서 주문 가능한 대체 메뉴를 찾는다."""
    target = next((m for m in menus if m["name"] == sold_out_name), None)
    if not target:
        return []
    candidates = [m for m in menus if not m["sold_out"] and m["name"] != sold_out_name]
    same_cat = [m for m in candidates if m["category"] == target["category"]]
    pool = same_cat or [m for m in candidates if m.get("caffeine", True) == target.get("caffeine", True)]
    tags = set(target.get("tags", []))
    pool.sort(key=lambda m: (-len(tags & set(m.get("tags", []))), abs(m["price"] - target["price"]), m["id"]))
    return [m["name"] for m in pool[:limit]]
