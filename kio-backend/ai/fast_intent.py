# [fast_intent.py] 사용자 말을 LLM 없이 '정규식 규칙'으로 먼저 분류하는 빠른 분류기.
# 확실하면 의도(recommend / qa / order / coupon / payment / order_and_pay)를 바로 돌려주고,
# 애매하면 None 을 돌려줘서 intent.py 의 LLM 분류가 이어받는다.
# ※ 겹치는 조건을 볼 때는 fast_classify() 안의 '검사 순서'(위→아래)가 곧 우선순위다.
import re
from typing import Optional

from ai.entity import extract_menu
from ai.korean import normalize_text, rx as _rx
from ai.payment import extract_payment_method



# ──── 의도 판별용 정규식 ────
# 질문 표현(물음표·가격·칼로리·'있나요' 등). 걸리면 대부분 '주문이 아니라 질문(qa)'으로 본다.
# [겹침→수정함] '있어요'가 _RE_COUPON_ACT 에도 있어서 '쿠폰 있어요'가 질문으로 판정되던 문제는,
#        쿠폰 단어 바로 뒤의 '있어요'만 질문 표지에서 빼도록(_RE_COUPON_HAVE) 고쳤다.
_RE_QUESTION = _rx(
    r"\?|얼마|가격|칼로리|당류|성분|알레르기|뭐예요|뭐에요|뭔가요|뭐야|뭐가|뭐지|어때|어떤|어디|언제|몇|"
    r"되나요|돼요|되나|되요|가능한가|있나요|있어요|있을까|없나요|알려|궁금|차이|혜택|정보|어떻게|왜|"
    r"결제하면|계산하면|나와요|나오나|나옵"
)
# 추천 관련 단어(넓게 잡음). 아래 _RE_RECO_REQUEST 는 '추천해줘'처럼 명확하게 추천을 부탁하는 말.
_RE_RECOMMEND = _rx(r"추천|골라줘|골라주|뭐마실|뭐먹|맛있는거|인기")
_RE_RECO_REQUEST = _rx(r"추천해줘|추천해주세요|추천해달라|추천좀|추천해봐|추천해요|추천해줄래|추천부탁")
# 결제 동사. [겹침] '할게|하겠'은 _RE_ORDER_VERB 에도 있다(결제 vs 주문 구분은 메뉴/결제수단 유무로 한다).
_RE_PAY_VERB = _rx(r"결제|계산|지불|페이로|카드로|쓸게|쓰겠|할게|하겠|해줘|해주세요|진행")
# 주문 동사. [겹침] menu_match._RE_ORDER_WORD, cart_command._RE_ORDER_TALK 와 비슷한 목록이 따로 있다.
_RE_ORDER_VERB = _rx(r"주세요|주셔|줘|줄래|주라|담아|담을게|넣어|주문|할게|하겠|부탁|드릴게|먹을게|마실게|시킬게|원해|원합니다")
# '디카페인 뭐 있어?' 류 질문 → recommend. [겹침] preference._RE_NO_CAFFEINE 도 디카페인/카페인 없음을 따로 판별한다.
_RE_CAFFEINE_ASK = _rx(r"(?:디카페인|카페인(?:이|은)?(?:없는|프리|안든|적은)).*(?:뭐|있|종류|메뉴|음료|거|것|알려|보여)|(?:뭐|어떤).*디카페인"
                       r"|카페인(?:이|은)?(?:들어간|들어있는|들은|든|있는|많은).*(?:뭐|종류|메뉴|음료|거|것|다|전부|모두|알려|보여)")
# '알려줘/보여줘'의 '줘'는 주문 동사가 아니라 정보 요청이다 → 디카페인·카페인 질문 판정에서만 이 말을 뺀 문장으로 주문 동사를 확인한다
_RE_INFO_VERB = _rx(r"알려줘|알려주세요|알려줄래|보여줘|보여주세요|보여줄래|말해줘")
# 쿠폰/바코드/상품권 언급, 그리고 그걸 '사용하겠다'는 행동 표현(_RE_COUPON_ACT).
_RE_COUPON = _rx(r"쿠폰|바코드|상품권|기프티콘")
_RE_COUPON_ACT = _rx(r"쓸게|쓰고|쓰려|사용|스캔|찍을|찍어|있어요|있는데|있습니다|있어|할게|등록")
# [수정] '쿠폰 있어요'처럼 쿠폰 단어 바로 뒤의 '있어요'는 질문이 아니라 "쿠폰이 있다"는 말이다.
#        (_RE_QUESTION 의 '있어요'와 겹쳐 coupon 빠른 경로를 못 타던 문제를 해결. 쿠폰 단어와 떨어진 '…있어요'는 그대로 질문 취급)
_RE_COUPON_HAVE = _rx(r"((?:쿠폰|바코드|상품권|기프티콘)(?:이|가|도|는|은)?)있어요")
# '2번으로', '첫번째' 같은 번호 선택. [겹침] entity.ORDINAL_KEYWORDS, cart_command._RE_ORD_N 와 같은 개념.
_RE_ORDINAL = _rx(r"\d+번(?:으로|째|거|걸|이요)?|[한두세네다섯]번째")
# '결제하면 영수증 나와요?' 같은 결제 관련 질문.
_RE_QA_PAY = _rx(r"(?:결제|계산)하면.*(?:영수증|나와요|나오나|나옵)|영수증")
# '할인되는 메뉴 줘' 같이 할인 대상 메뉴를 주문하는 표현.
_RE_DISCOUNT_MENU = _rx(r"할인(?:되는|받는|가능한|적용)?메뉴")
# 수량 표현(두 잔, 3개 …). [겹침] dialog._HAS_QTY, cart_command._RE_NEW_QTY, entity.extract_quantity 가 같은 일을 한다.
_RE_HAS_QTY = _rx(r"\d+(?:잔|개|병|컵)|[한두세네]잔|[한두세네]개|[한두세네]컵|다섯잔|다섯개|하나|둘|셋|넷")


# 빠른 의도 분류. 검사 순서(= 우선순위):
#  1) 빈 입력 → None
#  2) 결제 후 영수증 질문 → qa
#  3) 쿠폰 단어가 있으면 → 행동 표현이면 coupon, 아니면 None(LLM)  ('쿠폰 있어요'도 coupon)
#  4) 디카페인 질문(주문 표현 없음) → recommend
#  5) 추천 단어 → order(번호+주문동사) / None / recommend
#  6) 할인 메뉴 주문 → order
#  7) 질문 표현이면 → None (LLM 에 맡김)
#  8) 메뉴+결제수단: 결제동사까지 있으면 order_and_pay, 없으면 None
#  9) 메뉴 없이 결제 말만 → payment
# 10) 메뉴+주문동사/수량 → order, 번호+주문동사 → order
# 반환값 None = 확신 없음 → intent.classify_intent() 로 넘긴다.
def fast_classify(query: str, menu_names: Optional[list] = None) -> Optional[str]:
    t = normalize_text(query)
    if not t:
        return None

    # 먼저 계산해 두는 값들: 질문 여부 / 메뉴 / 결제수단 / 결제동사 유무
    is_question = bool(_RE_QUESTION.search(t))
    # [2] 결제 후 영수증 질문 → qa  ([겹침] _RE_QUESTION 의 '결제하면|나와요' 와 일부 중복)
    if _RE_QA_PAY.search(t) and not _RE_COUPON.search(t):
        return "qa"
    menu = extract_menu(query, menu_names) if menu_names else None
    method = extract_payment_method(query)
    has_pay_verb = bool(_RE_PAY_VERB.search(t))

    # [3] 쿠폰 계열: 질문이 아니고 + 사용 행동 표현이 있고 + 메뉴 말이 없을 때만 coupon
    if _RE_COUPON.search(t):
        coupon_question = bool(_RE_QUESTION.search(_RE_COUPON_HAVE.sub(r"\1", t)))  # [수정] '쿠폰 있어요'의 '있어요'는 질문 표지에서 제외
        if not coupon_question and _RE_COUPON_ACT.search(t) and not menu:
            return "coupon"
        return None

    # [4] 디카페인 질문. 주문 동사·수량·번호가 없을 때만 recommend
    if _RE_CAFFEINE_ASK.search(t) and not _RE_ORDER_VERB.search(_RE_INFO_VERB.sub("", t)) and not _RE_HAS_QTY.search(t) and not _RE_ORDINAL.search(t):
        return "recommend"

    # [5] 추천 단어가 있는 경우. '2번으로 주세요'처럼 번호+주문동사면 추천이 아니라 order
    if _RE_RECOMMEND.search(t):
        if _RE_ORDINAL.search(t) and _RE_ORDER_VERB.search(t) and not _RE_RECO_REQUEST.search(t):
            return "order"
        if menu and _RE_ORDER_VERB.search(t) and not re.search(normalize_text("추천"), t):
            return None
        return "recommend" if not menu else None

    # [6] '할인 메뉴 줘' → order (결제동사·질문 표현이 섞이면 제외)
    if _RE_DISCOUNT_MENU.search(t) and _RE_ORDER_VERB.search(t) and not menu and not has_pay_verb and not re.search(normalize_text("얼마|어떻게|뭐|나요|까요|있어요"), t):
        return "order"

    # [7-a] "디카페인 라떼 두 잔 줄래?" — 물음표만 있고 다른 질문 표현은 없는 '주문 요청'(메뉴 + 줘/줄래/주세요)은 order
    if (is_question and menu and _RE_ORDER_VERB.search(t)
            and not _RE_QUESTION.search(t.replace("?", "")) and not has_pay_verb and not method):
        return "order"

    # [7] 여기까지 안 걸렸는데 질문 표현이 있으면 확신 없음 → LLM
    if is_question:
        return None

    # [8] 메뉴 + 결제수단 + 결제동사 → order_and_pay / 메뉴+결제수단만이면 애매해서 None
    if menu and method and has_pay_verb:
        return "order_and_pay"
    if menu and method:
        return None

    # [9] 메뉴 없이 결제수단/결제 말만 → payment (번호 선택이 섞이면 None)
    if not menu and (method or re.search(normalize_text("결제|계산"), t)) and has_pay_verb:
        if _RE_ORDINAL.search(t):
            return None
        return "payment"

    # [10] 메뉴 + 주문동사/수량 → order. 아래는 '번호 + 주문동사'도 order
    if menu and (_RE_ORDER_VERB.search(t) or _RE_HAS_QTY.search(t)):
        return "order"

    if _RE_ORDINAL.search(t) and _RE_ORDER_VERB.search(t):
        return "order"

    return None
