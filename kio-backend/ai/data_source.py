"""ai 패키지가 메뉴·할인 데이터를 가져오는 창구.

예전에는 recommend.py / discount.py 가 `from app.admin import db` 를 맨 위에서 직접 불러서
ai 가 app(서버 코드)에 묶여 있었다. 이제는 이 파일의 함수만 부르고, 실제 DB 는 처음 필요할 때
(lazy) 불러온다. 테스트나 다른 저장소를 쓰고 싶으면 set_provider() 로 get_menus / get_discounts /
DISCOUNT_METHODS 를 가진 객체를 꽂으면 된다.
"""

_provider = None


# 데이터 제공 객체 교체(None 이면 기본값인 app.admin.db 로 되돌림)
def set_provider(provider) -> None:
    global _provider
    _provider = provider


def _db():
    if _provider is not None:
        return _provider
    from app.admin import db  # 처음 필요할 때만 불러온다
    return db


def get_menus() -> list:
    return _db().get_menus()


def get_discounts(active_only: bool = True) -> list:
    return _db().get_discounts(active_only=active_only)


def discount_methods() -> dict:
    return _db().DISCOUNT_METHODS


def get_analytics() -> dict:
    return _db().get_analytics()
