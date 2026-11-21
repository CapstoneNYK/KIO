"""세션(키오스크)별 대화 상태 저장소.

main.py 는 지금 '방금 추천한 메뉴 / 방금 물어본 메뉴 / 먼저 말한 온도'를 모듈 전역 리스트
(_last_recommended_menus, _last_asked, _pending_temp)로 들고 있어서, 키오스크가 두 대 이상이거나
손님이 바뀌면 상태가 서로 덮어써진다(마지막 사용 후 시간 제한도 없다).
이 모듈은 같은 세 값을 session_id 별로 나눠 담고, 일정 시간(기본 10분) 안 쓰면 지운다.

사용법(main.py 쪽):
    from ai.session import get_state
    st = get_state(request.session_id)          # session_id 가 없으면 "" 하나를 공유 = 지금과 동일
    st.last_recommended[:] = [...]              # 예전 _last_recommended_menus[:] = [...] 와 똑같이 사용
    st.last_asked.clear(); st.pending_temp[:] = [...]
cart_command.detect_cart_command(..., session_id=request.session_id) 도 같이 넘기면 된다.
"""
import time
from contextvars import ContextVar
from dataclasses import dataclass, field

SESSION_TTL_SEC = 600  # 10분 동안 아무 말도 없으면 그 세션 상태를 지운다


@dataclass
class ConversationState:
    last_recommended: list = field(default_factory=list)   # 방금 추천/안내한 메뉴 이름들 ("1번 주세요", "그걸로"의 대상)
    last_asked: list = field(default_factory=list)         # 방금 가격·재료 등을 물어본 메뉴 ("그럼 그걸로 주세요")
    pending_temp: list = field(default_factory=list)       # "따뜻한 커피"처럼 종류 고르기 전에 말한 온도 ('핫'/'아이스')
    touched: float = field(default_factory=time.time)      # 마지막으로 쓴 시각


_STATES: dict[str, ConversationState] = {}


# 세션의 상태를 돌려준다(없으면 새로 만든다). 호출할 때마다 마지막 사용 시각이 갱신되고, 오래된 세션은 정리된다.
def get_state(session_id: str = "") -> ConversationState:
    now = time.time()
    for sid in [k for k, v in _STATES.items() if now - v.touched > SESSION_TTL_SEC and k != session_id]:
        del _STATES[sid]
    st = _STATES.setdefault(session_id or "", ConversationState())
    st.touched = now
    return st


# 세션 상태 삭제(session_id 를 안 주면 전부)
def reset_state(session_id: str | None = None) -> None:
    if session_id is None:
        _STATES.clear()
    else:
        _STATES.pop(session_id, None)


# ── 지금 처리 중인 요청의 세션 ──
# 요청 처리 맨 앞에서 set_session(session_id) 를 부르면, 같은 요청 안의 어느 함수에서든 current_state() 로 그 세션 상태를 쓴다.
# (async 요청마다 ContextVar 가 따로라 서로 섞이지 않는다)
_SID: ContextVar[str] = ContextVar("session_id", default="")


def set_session(session_id: str) -> None:
    _SID.set(session_id or "")


def current_state() -> ConversationState:
    return get_state(_SID.get())
