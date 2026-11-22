# [quick_answers.py] LLM 없이 규칙·DB 로 바로 답하는 안내들. main.py 에서 분리했다.
#  인기 메뉴 / 할인 목록 / "아이스도 돼요?" 온도 가능 여부 / 이름이 겹치는 단어 되묻기 / '커피·스무디' 같은 종류 목록
# 밖에서 쓰는 패턴(RE_*, CATEGORY_ASK, DISCOUNT_QUESTION_PATTERN)은 이름 앞 밑줄을 뗐다.
import re

from ai import data_source
from ai.entity import extract_menu
from ai.followup import menu_words
from ai.korean import normalize_text
from ai.order import _josa


# 할인·쿠폰을 '물어보는' 표현(되나요/얼마/알려줘…)
DISCOUNT_QUESTION_PATTERN = re.compile(
    r"(\?|되나요|되나|돼요|되나여|가능해|가능한가|뭐야|뭐예요|뭔가요|얼마|무엇|알려줘)"
)


# '할인 뭐 있어요?' 같은 전체 할인 목록 질문 / 특정 수단(KT·쿠폰…)을 말한 경우 / 인기 메뉴 질문 — 모두 normalize_text 된 말에 쓰는 패턴
RE_DISCOUNT_INFO = re.compile(
    normalize_text(r"(?:할인|혜택).{0,8}(?:뭐|무엇|뭘|어떤|무슨|있|알려|종류)|(?:뭐|어떤|무슨).{0,6}(?:할인|혜택)")
)


# '전체적인 할인혜택'처럼 전부 보여 달라는 말이면 장바구니와 상관없이 모든 할인을 보여 준다
RE_DISCOUNT_ALL = re.compile(normalize_text(r"전체|모든|모두|전부|다\s*(?:알려|보여)|종류"))
RE_DISCOUNT_SPECIFIC = re.compile(normalize_text(r"kt|티멤버십|t멤버십|우주|cj|씨제이|쿠폰|바코드"))


RE_POPULAR = re.compile(
    normalize_text(r"잘나가|잘팔|베스트|많이(?:팔|시켜|주문|찾)|인기(?:메뉴|있는|많은|가많|제일|가장)|가장인기|제일인기|대표메뉴|시그니처")
)


# 진행 중인 할인 목록을 DB 에서 읽어 번호 목록 문구로 만든다(LLM 안 씀)
# 할인 설명 첫 줄에 '아이스 아메리카노 구매 시'처럼 특정 메뉴가 조건으로 적혀 있으면 그 메뉴(와 온도)를 돌려준다. 조건이 없으면 None
def _discount_menu_condition(first_line: str, menus: list[dict]) -> tuple[str, str | None] | None:
    names = sorted((m["name"] for m in menus), key=len, reverse=True)
    hit = next((n for n in names if n in first_line), None)
    if not hit:
        return None
    return hit, None  # 온도는 따지지 않는다(예: T멤버십은 핫/아이스 아메리카노 모두 대상)


# 받침 있으면 first, 없거나 한글이 아니면 second (영문으로 끝나는 이름은 '는/를' 로 읽는다)
def _pick(first: str, second: str, word: str) -> str:
    ch = word.strip()[-1:]
    return first if ch and "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 else second


def discount_info_answer(cart_items: list | None = None, menus: list[dict] | None = None, show_all: bool = False) -> str:
    """진행 중인 할인 안내. 장바구니에 메뉴가 담겨 있으면 그 주문에 지금 적용되는 할인만 보여 준다(메뉴 조건이 있는 할인은 해당 메뉴가 있을 때만)."""
    from ai.cart_command import parse_cart
    discounts = data_source.get_discounts(active_only=True)
    if not discounts:
        return "지금은 진행 중인 할인이 없어요."
    cart = [] if show_all else parse_cart(cart_items or [])
    menus = menus if menus is not None else data_source.get_menus()
    shown, hidden = [], []
    for d in discounts:
        first = (d.get("description") or "").strip().split("\n")[0]
        cond = _discount_menu_condition(first, menus) if cart else None
        if cond and not any(c["menu"] == cond[0] and (not cond[1] or c["temperature"] == cond[1]) for c in cart):
            hidden.append((d, cond))
            continue
        shown.append((d, first))
    if not shown:
        shown, hidden = [(d, (d.get("description") or "").strip().split("\n")[0]) for d in discounts], []
    lines = [f"{i}. **{d['name']}**: {first}" if first else f"{i}. **{d['name']}**" for i, (d, first) in enumerate(shown, 1)]
    head = "지금 담은 메뉴에 적용되는 할인이에요." if cart else "지금 받을 수 있는 할인이에요."
    tail = ""
    if hidden:  # 조건 메뉴가 없어서 빠진 할인은 한 줄로만 알려 준다
        d, (menu, temp) = hidden[0]
        label = ("아이스 " if temp == "ICE" else "따뜻한 " if temp == "HOT" else "") + menu
        name = f"**{d['name']}**"
        tail = f"\n{name}{_pick('은', '는', d['name'])} **{label}**{_pick('을', '를', label)} 담으면 받을 수 있어요."
    return head + "\n" + "\n".join(lines) + tail + "\n결제할 때 해당 수단을 선택하거나 '쿠폰 쓸게요'라고 말씀해 주세요."


# 최근 일주일 판매량 상위 3개(품절 제외)를 번호 목록으로 안내. (문구, 메뉴이름들) 반환 — 이름들은 '1번 주세요' 선택에 쓰인다
def popular_answer(menus: list[dict]) -> tuple[str, list[str]]:
    by_name = {m["name"]: m for m in menus}
    top = [t for t in data_source.get_analytics()["top_menus"]
           if t["name"] in by_name and not by_name[t["name"]]["sold_out"]][:3]
    if not top:
        return ("아직 집계된 판매 기록이 없어요. 원하시는 맛이나 온도를 말씀해 주시면 추천해 드릴게요.", [])
    lines = [f"{i}번 {t['name']}" for i, t in enumerate(top, 1)]  # 판매량 숫자는 보여 주지 않고 순위만
    return ("최근 일주일 동안 가장 많이 팔린 메뉴 순위예요.\n" + "\n".join(lines) +
            "\n번호로 말씀하시면 바로 담아드려요.", [t["name"] for t in top])


# '아이스 되나요?' 류 온도 가능 여부 질문 패턴(질문/원하는 온도/주문 말투)
_RE_TEMP_QUESTION = re.compile(normalize_text(r"가능|되나|돼요|될까|되려나|있나|있어요|있을까|할수|\?"))


_RE_WANT_HOT = re.compile(normalize_text(r"따뜻|뜨겁|뜨거|핫|안차갑|안시원|차갑지않|덜차갑|미지근"))


_RE_WANT_ICE = re.compile(normalize_text(r"아이스|차갑|시원|얼음"))


_RE_ORDER_WORDS = re.compile(normalize_text(r"주세요|줘|주라|담아|할게|주문"))


# '카페라떼 아이스로도 돼요?' → 메뉴의 temps 를 보고 가능/불가능을 바로 답한다. 주문 말투가 섞이면 None(주문으로 처리)
def temperature_answer(query: str, menus: list[dict]) -> str | None:
    qn = normalize_text(query)
    if not _RE_TEMP_QUESTION.search(qn) or _RE_ORDER_WORDS.search(qn):
        return None
    want = "HOT" if _RE_WANT_HOT.search(qn) else "ICE" if _RE_WANT_ICE.search(qn) else None
    name = extract_menu(query, [m["name"] for m in menus])
    if not want or not name:
        return None
    info = next((m for m in menus if m["name"] == name), None)
    temps = (info or {}).get("temps") or []
    if not temps:
        return None
    topic = _josa(name, "은", "는")
    if want in temps:
        return f"네, {topic} {'따뜻하게도' if want == 'HOT' else '아이스로도'} 주문할 수 있어요."
    only = "아이스" if "ICE" in temps else "따뜻한"
    return f"{topic} {only} 음료로만 주문할 수 있어요."


# '딸기'처럼 여러 메뉴 이름에 들어 있는 단어만 말하면 후보(최대 4개)를 번호 목록으로 되묻는다. 후보가 가장 적은 단어를 고른다
def ambiguous_menu_question(query: str, menus: list[dict]) -> tuple[str, list[str]] | None:
    qn = normalize_text(query)
    best: tuple[str, list[str]] | None = None
    for word in {w for m in menus for w in menu_words(m["name"])}:
        if normalize_text(word) not in qn:
            continue
        names = [m["name"] for m in menus if not m["sold_out"] and word in menu_words(m["name"])]
        if len(names) >= 2 and (best is None or len(names) < len(best[1])):
            best = (word, names[:4])
    if not best:
        return None
    word, names = best
    lines = "\n".join(f"{i}번 {n}" for i, n in enumerate(names, 1))
    return f"'{word}'가 들어간 메뉴가 여러 개예요. 어느 걸로 할까요?\n{lines}\n번호로 말씀해 주세요.", names


# '커피/차/주스/에이드/스무디'처럼 종류만 말하는 경우(정규식, 메뉴 카테고리, 부르는 말). 카테고리 이름은 메뉴 DB 의 category 값과 같아야 한다
_CATEGORY_WORDS = (  # 어르신이 메뉴 이름 대신 종류로 말하는 경우: (정규식, 메뉴 카테고리들, 부르는 말)
    (re.compile(r"커피"), ("커피",), "커피"),
    (re.compile(r"차(?![가-힣])|티(?![가-힣])"), ("티",), "차"),
    (re.compile(r"주스|쥬스|과일\s*음료"), ("주스",), "주스"),
    (re.compile(r"에이드"), ("에이드",), "에이드"),
    (re.compile(r"스무디"), ("스무디",), "스무디"),
)


# '스무디 종류 뭐 있어?' 같은 종류 목록 질문 표현
CATEGORY_ASK = re.compile(r"종류|뭐\s*(?:가\s*)?있|뭐뭐|어떤\s*(?:게|거|메뉴)|무슨\s*(?:게|거|메뉴)")


# 종류만 말했을 때 그 카테고리의 판매 가능 메뉴를 최대 4개까지 번호 목록으로 보여 준다
def category_question(query: str, menus: list[dict]) -> tuple[str, list[str]] | None:
    """"커피 하나 주세요"처럼 종류만 말했을 때 그 종류의 메뉴를 보여 주고 고르게 한다."""
    for rx, cats, label in _CATEGORY_WORDS:
        if not rx.search(query):
            continue
        names = [m["name"] for m in menus if m["category"] in cats and not m["sold_out"]]
        if not names:
            return None
        shown = names[:4]
        lines = "\n".join(f"{i}번 {n}" for i, n in enumerate(shown, 1))
        more = " 그 밖의 메뉴는 화면에서 볼 수 있어요." if len(names) > len(shown) else ""
        return f"{label}는 이런 메뉴가 있어요. 어느 걸로 드릴까요?\n{lines}\n번호나 이름으로 말씀해 주세요.{more}", shown
    return None


# ── "바닐라라떼 있어?" / "바닐라라떼 얼마야?" — 메뉴판(DB)만 보고 짧게 답한다(장바구니·할인 얘기는 하지 않는다) ──
RE_HAS_MENU = re.compile(normalize_text(r"있(?:어|나|니|습니까|을까)|팔(?:아|아요|까|고)|파나|파냐|판매"))
RE_PRICE_ASK = re.compile(normalize_text(r"얼마|가격|몇원|몇천원|비싸|값"))
# 주문하는 말이 섞여 있으면 이 안내가 아니라 주문 흐름이 맡는다
RE_ORDER_WORDS = re.compile(normalize_text(r"주세요|주라|줄래|담아|주문|(?<!알려)줘$|(?<!알려)줘요$|할게|하겠"))


# 질문에서 말한 메뉴들을 말한 순서대로 찾는다(긴 이름 우선, 겹치면 하나만)
def _menus_in(query: str, menus: list[dict]) -> list[dict]:
    qn = normalize_text(query)
    found, taken = [], []
    for m in sorted(menus, key=lambda m: -len(m["name"])):
        n = normalize_text(m["name"])
        pos = qn.find(n)
        if pos < 0 or any(not (pos + len(n) <= a or pos >= b) for a, b in taken):
            continue
        taken.append((pos, pos + len(n)))
        found.append((pos, m))
    return [m for _, m in sorted(found, key=lambda x: x[0])]


# "얼그레이 카페인 있어?" / "녹차라떼에 카페인 들어갔어?" — 서술형 질문만(카페인 없는/있는 + 명사 같은 추천·주문 표현은 제외)
RE_CAFFEINE_PRED = re.compile(normalize_text(
    r"카페인(?:이|은|도|좀)?\s*(?:있(?:어|나|니|는지|습니까|을까|죠)|없(?:어|나|니|는지|습니까|을까|죠)|들(?:어|었)|들어있|함유|포함|많|적|세|약|얼마)"
))
RE_CAFFEINE_NOT_ASK = re.compile(normalize_text(r"추천|골라|뭐가|어떤|종류|메뉴\s*(?:뭐|알려)"))


def caffeine_answer(query: str, menus: list[dict]) -> tuple[str, list[str]] | None:
    """특정 메뉴의 카페인 유무 질문에 관리자 메뉴 설정(caffeine)을 그대로 답한다. 메뉴를 말하지 않았거나 해당 없으면 None."""
    qn = normalize_text(query)
    if "카페인" not in qn or RE_ORDER_WORDS.search(qn) or RE_CAFFEINE_NOT_ASK.search(qn) or not RE_CAFFEINE_PRED.search(qn):
        return None
    found = _menus_in(query, menus)
    if not found or len(found) > 4:
        return None
    lines = []
    for m in found:
        name = m["name"]
        decaf = m["category"] == "디카페인" or name.startswith("디카페인")
        if m.get("caffeine", True):
            lines.append(f"{_josa(name, '은', '는')} 카페인이 들어 있어요.")
        elif decaf:
            lines.append(f"{_josa(name, '은', '는')} 카페인을 뺀 메뉴라 카페인이 거의 없어요.")
        elif re.search(r"초코|코코아|모카|오레오", name):  # 코코아에는 카페인이 아주 조금 들어 있다
            lines.append(f"{_josa(name, '은', '는')} 카페인이 거의 없어요. 초코 성분 때문에 아주 소량 들어 있을 수 있어요.")
        else:
            lines.append(f"{_josa(name, '은', '는')} 카페인이 없어요.")
    return " ".join(lines), [m["name"] for m in found]


def _won(price: int) -> str:
    return f"{price:,}원"


def menu_info_answer(query: str, menus: list[dict]) -> tuple[str, list[str]] | None:
    """메뉴 이름이 들어 있는 '있어요?' / '얼마예요?' 질문의 답(문구, 메뉴 이름들). 해당 없으면 None."""
    qn = normalize_text(query)
    if RE_ORDER_WORDS.search(qn):
        return None
    asks_price, asks_has = bool(RE_PRICE_ASK.search(qn)), bool(RE_HAS_MENU.search(qn))
    if not (asks_price or asks_has):
        return None
    found = _menus_in(query, menus)
    if not found or len(found) > 3:
        return None
    names = [m["name"] for m in found]
    if asks_price:  # 가격만 짧게
        parts = [f"{m['name']}{'은' if _has_batchim(m['name']) else '는'} {_won(m['price'])}" for m in found]
        sold = [m["name"] for m in found if m.get("sold_out")]
        tail = f" {', '.join(sold)}{'은' if _has_batchim(sold[-1]) else '는'} 지금 품절이에요." if sold else ""
        return ", ".join(parts) + "이에요." + tail, names
    lines = []
    for m in found:
        if m.get("sold_out"):
            lines.append(f"{m['name']}{'은' if _has_batchim(m['name']) else '는'} 있지만 지금 품절이에요.")
        else:
            lines.append(f"네, {m['name']}{'은' if _has_batchim(m['name']) else '는'} 있어요. {_won(m['price'])}이에요.")
    return " ".join(lines), names


def _has_batchim(word: str) -> bool:
    ch = word.strip()[-1:]
    return bool(ch) and "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0


# ── 사이즈 질문: 이 매장은 한 가지 사이즈만 판매한다 ──
RE_SIZE_WORD = re.compile(normalize_text(
    r"사이즈|크기|라지|스몰|미디엄|톨|그란데|벤티|큰거|큰걸|큰것|큰사이즈|작은거|작은걸|작은것|용량|몇ml|몇온스|양많이|양을?많이|곱빼기"))
SIZE_ANSWER = "저희는 **원사이즈**라서 **16oz** 한 가지 사이즈만 가능해요."


def size_answer(query: str, menus: list[dict]) -> str | None:
    """"사이즈 뭐 있어요?" / "라지로 주세요" — 사이즈를 고를 수 없다고 안내한다. 사이즈 말이 없으면 None."""
    qn = normalize_text(query)
    if not RE_SIZE_WORD.search(qn):
        return None
    if RE_ORDER_WORDS.search(qn) and _menus_in(query, menus):
        return None  # "아메리카노 라지로 주세요"는 주문 흐름이 받는다
    return SIZE_ANSWER
