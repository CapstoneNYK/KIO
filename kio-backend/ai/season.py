# [season.py] 계절을 따진 추천. 겨울엔 따뜻하게 마실 수 있는 메뉴를, 여름엔 시원한 메뉴를 먼저 보여 준다.
# (아이스 아메리카노는 겨울에도 많이 마시니 겨울에도 밀리지 않게 둔다.) 규칙 추천의 정렬, 시간대 추천의 기본 목록, LLM 추천 프롬프트가 같이 쓴다.
from datetime import datetime


def today() -> datetime:  # 테스트에서 날짜를 바꿔 끼울 수 있게 따로 둔다
    return datetime.now()


def season_of(month: int) -> str:
    if month in (11, 12, 1, 2):  # 한국은 11월부터 쌀쌀해져 따뜻한 음료가 먼저 나가기 시작한다
        return "겨울"
    if month in (6, 7, 8):
        return "여름"
    return "봄가을"


# 작을수록 먼저 보여 준다
def seasonal_rank(menu: dict, season: str) -> int:
    temps = set(menu.get("temps") or [])
    if season == "겨울":
        if "HOT" in temps or "아메리카노" in menu["name"]:  # 따뜻하게 되는 메뉴 + 겨울에도 잘 나가는 아이스 아메리카노
            return 0
        return 1  # 차갑게만 되는 메뉴(스무디·에이드·주스 등)
    if season == "여름":
        if temps == {"ICE"}:
            return 0
        return 1 if "ICE" in temps else 2
    return 0


def sort_by_season(menus: list, now: datetime | None = None) -> list:
    season = season_of((now or today()).month)
    return sorted(menus, key=lambda m: (seasonal_rank(m, season), m["id"]))  # 같은 순위끼리는 원래(id) 순서


# LLM 추천 프롬프트에 넣을 한 줄. 봄·가을은 따로 안내하지 않는다
def season_hint(now: datetime | None = None) -> str:
    season = season_of((now or today()).month)
    if season == "겨울":
        return ("지금은 겨울이라 따뜻한 음료가 더 많이 나가요. 따뜻하게 마실 수 있는 메뉴를 먼저 권하세요. "
                "차갑게만 되는 메뉴는 손님이 원할 때만 권하고, 아이스 아메리카노는 겨울에도 인기가 많아 권해도 좋아요.")
    if season == "여름":
        return "지금은 여름이라 시원한 음료가 더 많이 나가요. 차갑게 마실 수 있는 메뉴를 먼저 권하세요."
    return "계절은 따로 고려하지 않아도 됩니다."
