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


RE_DISCOUNT_SPECIFIC = re.compile(normalize_text(r"kt|티멤버십|t멤버십|우주|cj|씨제이|쿠폰|바코드"))


RE_POPULAR = re.compile(
    normalize_text(r"잘나가|잘팔|베스트|많이(?:팔|시켜|주문|찾)|인기(?:메뉴|있는|많은|가많|제일|가장)|가장인기|제일인기|대표메뉴|시그니처")
)


# 진행 중인 할인 목록을 DB 에서 읽어 번호 목록 문구로 만든다(LLM 안 씀)
def discount_info_answer() -> str:
    discounts = data_source.get_discounts(active_only=True)
    if not discounts:
        return "지금은 진행 중인 할인이 없어요."
    lines = []
    for i, d in enumerate(discounts, 1):
        first = (d.get("description") or "").strip().split("\n")[0]
        lines.append(f"{i}. {d['name']}: {first}" if first else f"{i}. {d['name']}")
    return ("지금 받을 수 있는 할인이에요.\n" + "\n".join(lines) +
            "\n결제할 때 해당 수단을 선택하거나 '쿠폰 쓸게요'라고 말씀해 주세요.")


# 최근 일주일 판매량 상위 3개(품절 제외)를 번호 목록으로 안내. (문구, 메뉴이름들) 반환 — 이름들은 '1번 주세요' 선택에 쓰인다
def popular_answer(menus: list[dict]) -> tuple[str, list[str]]:
    by_name = {m["name"]: m for m in menus}
    top = [t for t in data_source.get_analytics()["top_menus"]
           if t["name"] in by_name and not by_name[t["name"]]["sold_out"]][:3]
    if not top:
        return ("아직 집계된 판매 기록이 없어요. 원하시는 맛이나 온도를 말씀해 주시면 추천해 드릴게요.", [])
    lines = [f"{i}번 {t['name']} ({t['count']}잔 판매)" for i, t in enumerate(top, 1)]
    return ("최근 일주일 동안 가장 많이 팔린 메뉴예요.\n" + "\n".join(lines) +
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
