import re
from typing import Optional

from ai.entity import extract_menu, normalize_text
from ai.payment import extract_payment_method


def _rx(pattern: str) -> "re.Pattern":
    return re.compile(normalize_text(pattern))

_RE_QUESTION = _rx(
    r"\?|얼마|가격|칼로리|당류|성분|알레르기|뭐예요|뭐에요|뭔가요|뭐야|뭐가|뭐지|어때|어떤|어디|언제|몇|"
    r"되나요|돼요|되나|되요|가능한가|있나요|있어요|있을까|없나요|알려|궁금|차이|혜택|정보|어떻게|왜|"
    r"결제하면|계산하면|나와요|나오나|나옵"
)
_RE_RECOMMEND = _rx(r"추천|골라줘|골라주|뭐마실|뭐먹|맛있는거|인기")
_RE_RECO_REQUEST = _rx(r"추천해줘|추천해주세요|추천해달라|추천좀|추천해봐|추천해요|추천해줄래|추천부탁")
_RE_PAY_VERB = _rx(r"결제|계산|지불|페이로|카드로|쓸게|쓰겠|할게|하겠|해줘|해주세요|진행")
_RE_ORDER_VERB = _rx(r"주세요|주셔|줘|줄래|주라|담아|담을게|넣어|주문|할게|하겠|부탁|드릴게|먹을게|마실게|시킬게|원해|원합니다")
_RE_COUPON = _rx(r"쿠폰|바코드|상품권|기프티콘")
_RE_COUPON_ACT = _rx(r"쓸게|쓰고|쓰려|사용|스캔|찍을|찍어|있어요|있는데|있습니다|있어|할게|등록")
_RE_ORDINAL = _rx(r"\d+번(?:으로|째|거|걸|이요)?|[한두세네다섯]번째")
_RE_HAS_QTY = _rx(r"\d+(?:잔|개|병)|한잔|두잔|세잔|네잔|하나|둘|셋|한개|두개")


def fast_classify(query: str, menu_names: Optional[list] = None) -> Optional[str]:
    t = normalize_text(query)
    if not t:
        return None

    is_question = bool(_RE_QUESTION.search(t))
    menu = extract_menu(query, menu_names) if menu_names else None
    method = extract_payment_method(query)
    has_pay_verb = bool(_RE_PAY_VERB.search(t))

    if _RE_COUPON.search(t):
        if not is_question and _RE_COUPON_ACT.search(t) and not menu:
            return "coupon"
        return None

    if _RE_RECOMMEND.search(t):
        if _RE_ORDINAL.search(t) and _RE_ORDER_VERB.search(t) and not _RE_RECO_REQUEST.search(t):
            return "order"
        if menu and _RE_ORDER_VERB.search(t) and not re.search(normalize_text("추천"), t):
            return None
        return "recommend" if not menu else None

    if is_question:
        return None

    if menu and method and has_pay_verb:
        return "order_and_pay"
    if menu and method:
        return None

    if not menu and (method or re.search(normalize_text("결제|계산"), t)) and has_pay_verb:
        if _RE_ORDINAL.search(t):
            return None
        return "payment"

    if menu and (_RE_ORDER_VERB.search(t) or _RE_HAS_QTY.search(t)):
        return "order"

    if _RE_ORDINAL.search(t) and _RE_ORDER_VERB.search(t):
        return "order"

    return None
