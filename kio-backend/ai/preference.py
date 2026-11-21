# [preference.py] '달콤하고 시원한 카페인 없는 거 3개 추천해줘' 같은 취향 문장을 규칙(정규식)으로 조건(Conditions)으로 바꾸고,
# 조건에 맞는 메뉴를 골라 추천 문구를 만든다(LLM 을 쓰지 않는 추천). LLM 기반 추천/QA 는 recommend.py 에 있다.
import re
from dataclasses import dataclass, field
from typing import Optional

from ai.vocab import HOT_CORE, HOT_EXTRA_PREFERENCE, ICE_CORE, ICE_EXTRA_PREFERENCE
from ai.korean import NUM_WORDS_5, normalize_text, rx as _rx, to_int



# 맛 표현 → 태그(12개). [겹침] menu_analyzer.ALLOWED_TAGS 와 같은 12개 목록이라, 태그를 추가/삭제하면 두 파일을 같이 고쳐야 한다.
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

# 부정 표현('안 단', '달지 않은')이 들어 있으면 그 맛을 '제외 태그'로 처리. 긍정 태그보다 먼저 처리하고 해당 말은 지워서 긍정 태그로 오인되지 않게 한다.
_NEGATED_TAGS = [
    # [수정함] 예전에는 이 줄에 '안쓴|안쓰|쓰지않'이 있어서 '안 쓴 걸로'가 '쌉쌀'이 아니라 '달콤' 제외로 처리됐다(아래 쌉쌀 줄은 말이 이미 지워져 도달 못 함).
    #         지금은 그 표현이 쌉쌀 줄에 있다.
    (_rx(r"안달|덜달|달지않|달지는않|안단|덜단|단거말고"), "달콤"),  # [수정] 안쓴|안쓰|쓰지않 은 아래 쌉쌀 규칙으로 옮김
    (_rx(r"안쓴|안쓰|쓰지않|안쌉|덜쓴|덜쌉"), "쌉쌀"),  # [수정] 안쓰 추가(기존엔 달콤 규칙에 있던 '안쓰')
    (_rx(r"안시|시지않|안새콤|안상큼"), "상큼"),
]

# 온도 표현. [겹침] dialog._HOT/_ICE, cart_command._RE_HOT/_RE_ICE/_HOT_W/_ICE_W, dictionary.ATTRIBUTE_KEYWORDS 와 단어 목록이 조금씩 다르다
_RE_HOT = _rx("|".join([HOT_CORE, HOT_EXTRA_PREFERENCE]))
_RE_ICE = _rx("|".join([ICE_CORE, ICE_EXTRA_PREFERENCE]))

# 카페인 없음 / 카페인 있음 표현. [겹침] fast_intent._RE_CAFFEINE_ASK 도 디카페인 질문을 따로 판별한다. ('피곤/졸려'는 카페인 있는 쪽으로 해석)
_RE_NO_CAFFEINE = _rx(r"카페인(?:이|은|을|도)?(?:없|빼|안|적|낮|약|프리)|디카페인|잠못자|잠이안")
_RE_CAFFEINE = _rx(r"카페인(?:이|은|을)?(?:있|충전|많|듬뿍)|잠깨|졸려|졸리|졸린|졸음|각성|피곤")

# 음료 종류 말 → 카테고리(스무디/에이드/주스/티). '티'는 '티켓' 등 제외 패턴 포함
_CATEGORY_PATTERNS = [
    (_rx(r"스무디"), ["스무디"]),
    (_rx(r"에이드"), ["에이드"]),
    (_rx(r"주스"), ["주스"]),
    (_rx(r"티(?!켓)|(?<!아|따|시|차)차(?!가|갑|분)|허브티"), ["티"]),
]
# '커피/라떼/아메리카노' — 커피 계열 언급. _RE_NOT_COFFEE 는 '커피 말고' 같은 제외 표현
_RE_COFFEE = _rx(r"커피|라떼|아메리카노")
_RE_NOT_COFFEE = _rx(r"커피말고|커피빼고|커피는빼|논커피|커피말구|커피안|커피제외|커피아닌")
# 커피로 묶는 카테고리(커피 + 디카페인)
_COFFEE_CATEGORIES = ["커피", "디카페인"]

# '저렴/가성비' — 가격 정렬 요청
_RE_CHEAP = _rx(r"저렴|싼거|싸게|싼음료|가성비|제일싼|가장싼")
# 가격 상한 표현('5천원 이하', '4500원 미만') / _RE_PRICE_KO 는 한글 숫자('삼천원 이하')
_RE_PRICE_DIGIT = _rx(r"(\d+(?:,\d{3})*)(천|만)?원?(?:이하|미만|아래|밑|이내|까지|안쪽|보다싼|보다저렴)")
_KO_DIGIT = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_RE_PRICE_KO = _rx(r"([일이삼사오육칠팔구])(천|만)원?(?:이하|미만|아래|밑|이내|까지|안쪽)")

# 추천 개수 숫자 변환표. [겹침] entity / dialog / cart_command 의 숫자 단어표와 같은 종류
_NUM_WORDS = NUM_WORDS_5
# '3개만', '두 가지' — 추천 개수 지정(1~MAX_LIMIT 로 제한)
_RE_LIMIT = _rx(r"(\d+|한|하나|두|둘|세|셋|네|넷|다섯)(?:(?:개|가지|종류|잔)(?:만|정도|씩)?|만)")

# 추천 최대 개수 / 기본 개수
MAX_LIMIT = 5
DEFAULT_LIMIT = 3


# 추천 조건 묶음. 온도·카페인·맛 태그·제외 태그·카테고리·가격 상한·저렴 정렬·개수
@dataclass
class Conditions:
    temperature: Optional[str] = None
    caffeine: Optional[bool] = None
    tags: list = field(default_factory=list)
    exclude_tags: list = field(default_factory=list)
    categories: list = field(default_factory=list)
    exclude_categories: list = field(default_factory=list)
    max_price: Optional[int] = None
    cheap: bool = False
    limit: Optional[int] = None

    # 조건이 하나도 없는지(없으면 추천 규칙으로 처리하지 않음)
    def is_empty(self) -> bool:
        return not (
            self.temperature or self.caffeine is not None or self.tags or self.exclude_tags
            or self.categories or self.exclude_categories or self.max_price or self.cheap
        )

    # 조건을 '카페인 없는 달콤한 시원한 커피' 같은 문구로 변환(안내문 머리말용)
    def describe(self, tags: Optional[list] = None) -> str:
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

# 태그 → 형용사 표현(안내문용) / _TAG_EXCLUDE_ADJ 는 제외 태그 표현
_TAG_ADJ = {
    "산미": "산미 있는", "상큼": "상큼한", "달콤": "달콤한", "고소": "고소한", "쌉쌀": "쌉쌀한",
    "진한": "진한", "부드러운": "부드러운", "향긋": "향긋한", "과일": "과일 맛", "탄산": "탄산이 있는",
    "깔끔": "깔끔한", "상쾌": "상쾌한",
}
_TAG_EXCLUDE_ADJ = {"달콤": "달지 않은", "쌉쌀": "쓰지 않은", "상큼": "시지 않은"}


# 가격 상한 추출: 숫자+천/만 단위 → 원 단위로 변환. 100 미만 숫자는 가격으로 보지 않음. 한글 숫자도 처리
def _parse_price(text_norm: str) -> Optional[int]:
    m = _RE_PRICE_DIGIT.search(text_norm)
    if m:
        value = int(m.group(1).replace(",", ""))
        unit = m.group(2)
        if unit == "천":
            value *= 1000
        elif unit == "만":
            value *= 10000
        elif value < 100:
            return None
        return value
    m = _RE_PRICE_KO.search(text_norm)
    if m:
        value = _KO_DIGIT[m.group(1)]
        return value * (1000 if m.group(2) == "천" else 10000)
    return None


# 문장 → Conditions. 순서: 온도(둘 다 말하면 무시) → 카페인 → 카테고리 → 부정 태그 → 긍정 태그 → 가격 → 저렴 → 개수
def parse_conditions(text: str) -> Conditions:
    t = normalize_text(text)
    c = Conditions()

    # 온도: 한쪽만 말했을 때만 인정
    hot, ice = bool(_RE_HOT.search(t)), bool(_RE_ICE.search(t))
    if hot and not ice:
        c.temperature = "HOT"
    elif ice and not hot:
        c.temperature = "ICE"

    # 카페인 조건 (없음 우선)
    if _RE_NO_CAFFEINE.search(t):
        c.caffeine = False
    elif _RE_CAFFEINE.search(t):
        c.caffeine = True

    # 카테고리: '커피 말고' → 커피 계열 제외 / 종류 단어 → 해당 카테고리 / 커피 단어만 있으면 커피 계열
    if _RE_NOT_COFFEE.search(t):
        c.exclude_categories = list(_COFFEE_CATEGORIES)
    for rx, cats in _CATEGORY_PATTERNS:
        if rx.search(t):
            c.categories.extend(cats)
    if not c.exclude_categories and not c.categories and (_RE_COFFEE.search(t) or "디카페인" in t):
        c.categories = list(_COFFEE_CATEGORIES)

    # 태그: 부정 표현을 먼저 제외 태그로 빼고 그 말을 지운 뒤, 남은 말에서 긍정 태그를 찾는다
    scrubbed = t
    for rx, tag in _NEGATED_TAGS:
        if rx.search(scrubbed):
            if tag not in c.exclude_tags:
                c.exclude_tags.append(tag)
            scrubbed = rx.sub("", scrubbed)
    for rx, tag in _TAG_PATTERNS:
        if rx.search(scrubbed) and tag not in c.tags and tag not in c.exclude_tags:
            c.tags.append(tag)

    # 가격 상한 / 저렴 정렬
    c.max_price = _parse_price(t)
    c.cheap = bool(_RE_CHEAP.search(t))

    # 추천 개수(1~5)
    m = _RE_LIMIT.search(t)
    if m:
        g = m.group(1)
        n = to_int(g, _NUM_WORDS, DEFAULT_LIMIT)
        c.limit = max(1, min(n, MAX_LIMIT))
    return c


# 메뉴 하나가 조건에 맞는지: 품절 제외 → 온도 → 카페인 → 카테고리 포함/제외 → 태그 포함/제외 → 가격
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


# 정렬: 저렴 요청이면 가격순, 아니면 메뉴 id 순
def _rank(menus: list, c: Conditions) -> list:
    if c.cheap:
        return sorted(menus, key=lambda m: (m["price"], m["id"]))
    return sorted(menus, key=lambda m: m["id"])

# 디카페인 메뉴인지(카테고리 또는 이름)
def _is_decaf(menu: dict) -> bool:
    return menu["category"] == "디카페인" or menu["name"].startswith("디카페인")


# 카테고리 그룹 규칙: 디카페인은 '커피'와 같은 계열로 묶어 섞어 보여 줌
_FAMILY = {"디카페인": "커피"}


# 추천을 여러 종류가 골고루 나오도록 카테고리별로 번갈아 뽑는다
def _diversify(menus: list, limit: int) -> list:
    groups: dict = {}
    for m in menus:
        groups.setdefault(_FAMILY.get(m["category"], m["category"]), []).append(m)
    out: list = []
    while len(out) < limit and any(groups.values()):
        for g in groups.values():
            if g and len(out) < limit:
                out.append(g.pop(0))
    return out


# 추천 결과: 안내 문구 / 추천 메뉴 이름들 / 완화한(뺀) 조건 / 찾았는지 여부
@dataclass
class Recommendation:
    answer: str
    menus: list
    relaxed: list = field(default_factory=list)
    found: bool = True


# 추천 목록에 보일 이름. 온도를 말했으면 '핫 …'/'아이스 …'를 붙임
def _display_name(menu: dict, c: Conditions) -> str:
    if c.temperature == "HOT":
        return f"핫 {menu['name']}"
    if c.temperature == "ICE" and "HOT" in menu.get("temps", []):
        return f"아이스 {menu['name']}"
    return menu["name"]


# 조건 기반 추천 메인 함수. 흐름:
#  1) 조건 파싱(비어 있으면 None) → 2) 조건에 맞는 메뉴 필터. 맛 태그 때문에 0건이면 뒤쪽 태그부터 하나씩 빼며 재시도(완화)
#  3) 그래도 없으면 '찾지 못했어요' 안내 → 4) 카페인 없음 요청이면 디카페인 우선 → 5) 정렬·다양화 → 6) 안내문 생성
def recommend_by_conditions(text: str, menus: list) -> Optional[Recommendation]:
    c = parse_conditions(text)
    if c.is_empty():
        return None

    # 추천 개수 / 필수 태그 목록 / 완화한 태그 기록
    limit = c.limit or DEFAULT_LIMIT
    required = list(c.tags)
    relaxed = []

    # 조건에 맞는 메뉴가 없으면 태그를 하나씩 빼면서 다시 찾는다(태그가 없어지면 중단)
    while True:
        matched = [m for m in menus if _matches(m, c, required)]
        if matched or not required:
            break
        relaxed.append(required.pop())

    # 끝내 없으면 '찾지 못했어요' 안내
    if not matched:
        return Recommendation(
            answer="죄송해요, 말씀하신 조건에 맞는 주문 가능한 메뉴를 찾지 못했어요. "
                   "온도나 종류를 바꿔서 다시 말씀해 주시겠어요?",
            menus=[], found=False,
        )

    # 카페인 없는 걸 원하고 종류 지정이 없으면 디카페인 메뉴를 우선
    if c.caffeine is False and not c.categories:
        decaf = [m for m in matched if _is_decaf(m)]
        if decaf:
            matched = decaf

    # 정렬(저렴순/태그 일치 많은 순) 후, 종류 지정이 없으면 다양하게 섞어서 개수만큼 선택
    picked = _rank(matched, c)
    if required and not c.cheap:
        picked.sort(key=lambda m: (-len(set(required) & set(m.get("tags", []))), m["id"]))
    picked = _diversify(picked, limit) if (not c.categories and not c.cheap) else picked[:limit]

    lines = [f"{i}. {_display_name(m, c)} ({m['price']:,}원)" for i, m in enumerate(picked, 1)]

    # 안내 머리말 + 번호 목록. 조건을 완화했으면 '그 조건을 빼고 골라봤어요'로 알려 준다
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


# 품절 메뉴의 대체 메뉴: 같은 카테고리(없으면 카페인 여부가 같은 메뉴) 중 태그가 많이 겹치고 가격이 비슷한 순
def find_alternatives(sold_out_name: str, menus: list, limit: int = 2) -> list:
    target = next((m for m in menus if m["name"] == sold_out_name), None)
    if not target:
        return []
    candidates = [m for m in menus if not m["sold_out"] and m["name"] != sold_out_name]
    same_cat = [m for m in candidates if m["category"] == target["category"]]
    pool = same_cat or [m for m in candidates if m.get("caffeine", True) == target.get("caffeine", True)]
    tags = set(target.get("tags", []))
    pool.sort(key=lambda m: (-len(tags & set(m.get("tags", []))), abs(m["price"] - target["price"]), m["id"]))
    return [m["name"] for m in pool[:limit]]
