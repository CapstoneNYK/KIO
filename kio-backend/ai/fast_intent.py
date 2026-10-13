"""규칙 기반 빠른 의도 분류 (LLM 호출 전 단계).

왜 필요한가
- 의도 분류는 매 요청마다 LLM을 한 번 부른다(로컬 7B 기준 수백 ms~수 초).
- 대부분의 발화("아메리카노 두 잔 주세요", "카드로 결제할게요")는 규칙으로 확실히 판단된다.
- 그래서 **확실한 경우만** 규칙으로 즉시 결정하고, 애매하면 None을 돌려 기존 LLM 분류로 넘긴다.

원칙: 정밀도 우선. 틀리느니 모르겠다고 말하는 쪽(None)이 낫다.
"""

import re
from typing import Optional

from ai.entity import extract_menu, normalize_text
from ai.payment import extract_payment_method


def _rx(pattern: str) -> "re.Pattern":
    return re.compile(normalize_text(pattern))


# 질문·정보 요청 표현이 있으면 주문/결제로 단정하지 않는다
_RE_QUESTION = _rx(
    r"\?|얼마|가격|칼로리|당류|성분|알레르기|뭐예요|뭐에요|뭔가요|뭐야|뭐가|뭐지|어때|어떤|어디|언제|몇|"
    r"되나요|돼요|되나|되요|가능한가|있나요|있어요|있을까|없나요|알려|궁금|차이|혜택|정보|어떻게|왜"
)
_RE_RECOMMEND = _rx(r"추천|골라줘|골라주|뭐마실|뭐먹|맛있는거|인기")
_RE_PAY_VERB = _rx(r"결제|계산|지불|페이로|카드로|쓸게|쓰겠|할게|하겠|해줘|해주세요|진행")
_RE_ORDER_VERB = _rx(r"주세요|주셔|줘|줄래|주라|담아|담을게|넣어|주문|할게|하겠|부탁|드릴게|먹을게|마실게|시킬게|원해|원합니다")
_RE_COUPON = _rx(r"쿠폰|바코드|상품권|기프티콘")
_RE_COUPON_ACT = _rx(r"쓸게|쓰고|쓰려|사용|스캔|찍을|찍어|있어요|있는데|있습니다|있어|할게|등록")
_RE_ORDINAL = _rx(r"\d+번(?:으로|째|거|걸|이요)?|[한두세네다섯]번째")
_RE_HAS_QTY = _rx(r"\d+(?:잔|개|병)|한잔|두잔|세잔|네잔|하나|둘|셋|한개|두개")


def fast_classify(query: str, menu_names: Optional[list] = None) -> Optional[str]:
    """확실하면 의도 문자열, 아니면 None(→ LLM 분류)."""
    t = normalize_text(query)
    if not t:
        return None

    is_question = bool(_RE_QUESTION.search(t))
    menu = extract_menu(query, menu_names) if menu_names else None
    method = extract_payment_method(query)
    has_pay_verb = bool(_RE_PAY_VERB.search(t))

    # 쿠폰: 쿠폰 단어 + 사용 의사, 질문형 아님
    if _RE_COUPON.search(t):
        if not is_question and _RE_COUPON_ACT.search(t) and not menu:
            return "coupon"
        return None

    # 질문형은 qa/recommend 판단이 필요하므로 추천 키워드가 없으면 LLM에 맡긴다
    if _RE_RECOMMEND.search(t):
        if menu and _RE_ORDER_VERB.search(t) and not re.search(normalize_text("추천"), t):
            return None
        return "recommend" if not menu else None

    if is_question:
        return None

    # 결제수단 + 메뉴 → order_and_pay
    if menu and method and has_pay_verb:
        return "order_and_pay"
    if menu and method:
        return None  # "카드 아메리카노" 같은 불완전 발화는 LLM에

    # 결제만 (메뉴 없음)
    if not menu and (method or re.search(normalize_text("결제|계산"), t)) and has_pay_verb:
        if _RE_ORDINAL.search(t):
            return None
        return "payment"

    # 주문: 메뉴 + (수량 또는 주문 동사)
    if menu and (_RE_ORDER_VERB.search(t) or _RE_HAS_QTY.search(t)):
        return "order"

    # "1번으로 담아줘" (직전 추천 목록 참조)
    if _RE_ORDINAL.search(t) and _RE_ORDER_VERB.search(t):
        return "order"

    return None
