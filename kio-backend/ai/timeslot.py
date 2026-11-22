# [timeslot.py] "아침에 뭐 마시지?", "오후에 많이 나가는 거", "지금 시간에 인기 있는 거" 같은 시간대별 추천.
# 최근 30일 주문 기록에서 그 시간대에 많이 팔린 메뉴를 보여 주고, 기록이 부족하면 시간대에 어울리는 종류로 대신 추천한다.
import re
from datetime import datetime

from ai import data_source
from ai.korean import normalize_text
from ai import season as _season
from ai.season import season_of, sort_by_season

# (이름, 해당 시각들, 말 속 단어, 기록이 부족할 때 추천할 종류들)
_SLOTS = [
    ("아침", list(range(5, 11)), r"아침|모닝|오전", ["커피"]),
    ("점심", list(range(11, 14)), r"점심|런치", ["커피", "에이드"]),
    ("오후", list(range(14, 18)), r"오후|한낮|간식|티타임", ["에이드", "스무디"]),
    ("저녁", list(range(18, 22)), r"저녁|퇴근", ["티", "디카페인"]),
    ("밤", list(range(22, 24)) + list(range(0, 5)), r"밤에|늦은밤|야식|새벽", ["디카페인", "티"]),
]
_SLOT_RES = [(n, h, re.compile(normalize_text(p)), c) for n, h, p, c in _SLOTS]

# 겨울에는 차갑게만 되는 종류(에이드·스무디)를 기본 추천에서 뺀다
_WINTER_CATS = {"점심": ["커피", "티"], "오후": ["커피", "티"]}
_RE_NOW = re.compile(normalize_text(r"지금|이\s*시간|요즘\s*이\s*시간"))
# 시간대 말이 나왔어도 '추천/인기를 묻는 말'일 때만 다룬다
_RE_ASK = re.compile(normalize_text(r"뭐|추천|좋|많이|인기|잘나가|잘팔|베스트|어울|마시기|마실|먹을"))
# 주문·할인·결제 같은 다른 말이면 이 기능이 가로채지 않는다
_RE_OTHER = re.compile(normalize_text(r"주세요|담아|주문|할게|할인|쿠폰|결제|카드|얼마|가격|영업|몇시|언제|문닫|문열"))

MIN_RECORDS = 5  # 이 시간대 판매 기록이 이보다 적으면 통계 대신 기본 추천을 쓴다


def _slot_of(hour: int):
    for n, hours, rx, cats in _SLOT_RES:
        if hour in hours:
            return n, hours, cats
    return "낮", [hour], []


def detect_slot(query: str, now: datetime | None = None):
    """말에서 시간대를 찾는다. (이름, 시각들, 기본 종류들, '지금'인지) 또는 None"""
    qn = normalize_text(query)
    if not _RE_ASK.search(qn) or _RE_OTHER.search(qn):
        return None
    for n, hours, rx, cats in _SLOT_RES:
        if rx.search(qn):
            return n, hours, cats, False
    if _RE_NOW.search(qn):
        n, hours, cats = _slot_of((now or datetime.now()).hour)
        return n, hours, cats, True
    return None


def slot_answer(query: str, menus: list[dict], now: datetime | None = None) -> tuple[str, list[str]] | None:
    found = detect_slot(query, now)
    if not found:
        return None
    label, hours, cats, is_now = found
    if season_of((now or _season.today()).month) == "겨울":
        cats = _WINTER_CATS.get(label, cats)
    by_name = {m["name"]: m for m in menus}
    when = f"지금 시간대({label})에" if is_now else f"{label} 시간대에"

    rows = data_source.get_popular_by_hours(hours, days=30, limit=10)
    if sum(r["count"] for r in rows) >= MIN_RECORDS:
        top = [r["name"] for r in rows if r["name"] in by_name and not by_name[r["name"]]["sold_out"]][:3]
        if top:
            lines = [f"{i}번 {n}" for i, n in enumerate(top, 1)]
            return (f"{when} 가장 많이 팔린 메뉴예요.\n" + "\n".join(lines) + "\n번호로 말씀하시면 바로 담아드려요.", top)

    # 판매 기록이 부족하면 시간대에 어울리는 종류에서 골고루 고른다
    picked: list[str] = []
    pools = [[m["name"] for m in sort_by_season(menus) if m["category"] == c and not m["sold_out"]] for c in cats]  # 계절에 맞는 메뉴 먼저
    for i in range(3):
        for pool in pools:
            if i < len(pool) and len(picked) < 3 and pool[i] not in picked:
                picked.append(pool[i])
    if not picked:
        return None
    lines = [f"{i}번 {n}" for i, n in enumerate(picked, 1)]
    return (f"{when} 많이 찾는 메뉴 기록이 아직 적어서, 이 시간에 잘 어울리는 메뉴로 골라봤어요.\n"
            + "\n".join(lines) + "\n번호로 말씀하시면 바로 담아드려요.", picked)
