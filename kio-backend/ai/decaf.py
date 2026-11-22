# [decaf.py] 디카페인 말투 처리: '카페인 없는 라떼' → 디카페인 메뉴로 바꾸기, 디카페인 버전이 없는 메뉴를 원하면 알려 주기
import re

# '카페인 없는 라떼' → '디카페인 라떼' (메뉴판에 디카페인 버전이 있을 때만). 안 바꾸면 카페인 있는 일반 라떼가 주문된다
_RE_DECAF_WORDS = r"(?<!디)카페인\s*(?:이\s*)?(?:없는|안\s*들어간|안\s*든|빠진|뺀|프리)\s*"


def decaf_phrase(query: str, menus: list[dict]) -> str:
    if not re.search(_RE_DECAF_WORDS, query):
        return query
    for m in menus:
        name = m["name"]
        base = name[len("디카페인"):].strip() if name.startswith("디카페인") else ""
        if base:
            query = re.sub("(" + _RE_DECAF_WORDS + ")(?=" + r"\s*".join(map(re.escape, base)) + ")", "디카페인 ", query)
    return query


# '카페인 없는 카푸치노 줘' 처럼 디카페인을 원하는데 메뉴판에 디카페인 버전이 없는 경우 → 일반 메뉴로 바로 주문하지 않고 먼저 확인한다
_RE_TEMP_WORD = r"(?:아이스|핫|따뜻한|뜨거운|차가운|시원한)?\s*"


def decaf_unavailable(query: str, menus: list[dict]) -> dict | None:
    names = {m["name"] for m in menus}
    for m in menus:
        name = m["name"]
        if name.startswith("디카페인") or not m.get("caffeine") or f"디카페인 {name}" in names:
            continue
        base = r"\s*".join(map(re.escape, name))
        if re.search("(?:" + _RE_DECAF_WORDS + r"|디카페인\s*)" + _RE_TEMP_WORD + base, query):
            return m
    return None
