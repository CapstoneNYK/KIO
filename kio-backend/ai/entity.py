# [entity.py] 사용자 말에서 '메뉴·수량·온도·옵션·포장 여부'를 뽑아내는 파일(이 프로젝트의 말 해석 기반).
# 크게 세 부분: ① 음성인식(STT) 오타 교정 ② 한 가지 항목 추출(extract_*) ③ 여러 메뉴 주문 분해(extract_multi_order).
import re
from ai.stt_fixes import apply_custom_fixes
from typing import Dict, Optional
from ai.dictionary import MENU_KEYWORDS, ATTRIBUTE_KEYWORDS
from ai.vocab import LEVEL_MORE
from ai.korean import NUM_WORDS_4, NUM_WORDS_5, NUM_WORDS_10, _unify_ae_e, normalize_text, rx as _rx, to_int, unify_ae_e  # noqa: F401  (normalize_text 는 다른 파일들이 ai.entity 에서도 가져다 쓴다)

# 옵션 키워드 → 표준 옵션 이름(구버전 방식, '샤추가/셔츠가' 같은 STT 오인식 포함).
# [겹침] 아래 extract_option_details() 가 개수·정도까지 해석하는 신버전이다. 둘 다 결과에 들어간다(options / option_details).
OPTION_KEYWORDS = {
    "샷추가": "샷추가",
    "샷 추가": "샷추가",
    "샷넣어": "샷추가",
    "샷 넣어": "샷추가",
    "더블샷": "샷추가",
    "샤추가": "샷추가",
    "셔츠가": "샷추가",
    "연하게": "연하게",
    "약하게": "연하게",
    "연하게해줘": "연하게",
}

# 수량 단어 → 숫자 (한=1 … 열=10). [겹침] 이 파일의 _NUM_WORDS / _UNIT_NUM, dialog._COUNT_WORDS, cart_command._NUM_WORDS, preference._NUM_WORDS
QUANTITY_MAP = NUM_WORDS_10

# 번호 선택 표현('1번', '첫번째' …) → 숫자. [겹침] fast_intent._RE_ORDINAL, cart_command._RE_ORD_N
ORDINAL_KEYWORDS: dict[str, int] = {
    "첫번째": 1, "첫 번째": 1, "1번째": 1, "1번": 1, "일번": 1,
    "두번째": 2, "두 번째": 2, "2번째": 2, "2번": 2,
    "세번째": 3, "세 번째": 3, "3번째": 3, "3번": 3,
    "네번째": 4, "네 번째": 4, "4번째": 4, "4번": 4,
    "다섯번째": 5, "다섯 번째": 5, "5번째": 5, "5번": 5,
    "여섯번째": 6, "여섯 번째": 6, "6번째": 6, "6번": 6,
    "일곱번째": 7, "일곱 번째": 7, "7번째": 7, "7번": 7,
    "여덟번째": 8, "여덟 번째": 8, "8번째": 8, "8번": 8,
    "아홉번째": 9, "아홉 번째": 9, "9번째": 9, "9번": 9,
    "열번째": 10, "열 번째": 10, "10번째": 10, "10번": 10,  # 추천·검색 목록이 10개까지 나온다
}


# ──── ① 음성인식(STT) 오타 교정 규칙 ────
# 디카페인을 비슷한 소리로 잘못 들은 경우 교정
# 앞에 한글이 붙은 말("아이스티 카페인", "버블티 카페인")의 '티'는 메뉴 이름 끝이라 디카페인으로 고치지 않는다
_STT_DECAF = re.compile(r"(?<![가-힣])[디티키지띠]\s*카\s*[페패폐]\s*[인임]")
# '샷 추가'를 비슷한 소리로 잘못 들은 경우("셔츠가루", "셧추가", "숏추가", "샤츠 가루" …)
_STT_SHOT_ADD = re.compile(r"(?<![가-힣])(?:셔츠|셧|섯|샤츠|슛|숏|샷츠|셔터)\s*(?:가루|가르|추가|까루)")
# "샷 추가해 주세요"를 "셔츠 갈아주세요/셧 까라줘"로 들은 경우 — 뒤에 부탁 말(주세요·줘·해…)이 올 때만 고친다("셔츠 갈아입어요" 같은 말은 건드리지 않는다)
_STT_SHOT_ADD_VERB = re.compile(
    r"(?<![가-힣])(?:셔츠|셧|섯|샤츠|슛|숏|샷츠|셔터|샷|삿)\s*(?:갈아|가라|까라|갈라|까자|가자)(?=\s*(?:주|줘|줄|드려|해|할|하))")
# "디카페 라떼"처럼 '인'을 빼고 줄여 말한 경우도 디카페인으로(이미 '인'이 붙은 말은 위 규칙이 처리)
_STT_DECAF_SHORT = re.compile(r"(?<![가-힣])[디티키지띠]\s*카\s*[페패폐](?!\s*[인임])")
# '핫으로'를 잘못 들은 경우('하수로', '맛대' …)
_STT_HOT = re.compile(r"(?<![가-힣])(?:하수로|하스로|하쑤로|핫우로|하수루|핫으루|하슬로|맛대)(?![가-힣])")

# '샷 추가'를 잘못 들은 경우('찹/샵 추가' …)
_STT_SHOT = re.compile(r"(?:찹|챱|샵|삿|셧|샤)(?=\s*(?:을|를)?\s*(?:더\s*)?추가)")

# 'T' 한 글자를 '티'로 (예: T 종류 → 티 종류)
_STT_TEA_T = re.compile(r"(?<![A-Za-z])[Tt](?![A-Za-z])(?=\s*(?:로|가|를|는|은|종류|류|말고|계열|\b))")
_STT_DISCOUNT = re.compile(r"할인\s*(?:에\s*등|해택|헤택|혜택|에\s*택)")
_STT_QTY2 = re.compile(r"(?<![가-힣])[조주]\s*잔")
_STT_AA = re.compile(r"아바(?:랑|하라)")
# 어르신 발음·STT 에서 자주 틀리는 메뉴/단어 교정표 (패턴 → 올바른 말)
_STT_MENU = [  # 어르신 발음·STT에서 자주 틀리는 메뉴 이름
    (re.compile(r"아메리카[도오]"), "아메리카노"),
    (re.compile(r"카푸치[도누나오]"), "카푸치노"),
    (re.compile(r"카페\s*나[떼때]"), "카페라떼"),
    (re.compile(r"마[키끼]아[또토]"), "마키아토"),
    (re.compile(r"에스프레[쏘소]"), "에스프레소"),
    (re.compile(r"쥬스"), "주스"),
    (re.compile(r"주차\s*[대돼됐](?![가-힣])"), "주차돼"),  # '여기 주차돼?' -> '여기 주차대'(주차 가능 여부 질문)
    (re.compile(r"[머먼버][블뿔볼]\s*티"), "버블티"),  # 흑당머블티 -> 흑당버블티
    (re.compile(r"(?<![가-힣])이스(?![가-힣])"), "아이스"),
    (re.compile(r"(?<![가-힣])[팔필](?=\s*(?:많이|적게|조금|빼|추가|더\s*주|듬뿍|넉넉))"), "펄"),  # 펄 많이 -> 팔 많이  # "이스 아메리카노"
    (re.compile(r"연하[나내네계](?![가-힣])"), "연하게"),
    (re.compile(r"레[모몬]\s*[네나]이[드트도]"), "레몬에이드"),  # 레모네이드
    (re.compile(r"(?<=[가-힣])에이[트도]"), "에이드"),  # 레몬에이트·자몽에이도
    (re.compile(r"(?<![가-힣])아메(?!리)"), "아메리카노"),
    (re.compile(r"삼[성송동숭]\s*[페패]이"), "삼성페이"),  # 삼동페이
    (re.compile(r"애[플풀]\s*[페패]이"), "애플페이"),
    (re.compile(r"피곤(?=\s*(?:할게|할께|할래|하겠))"), "픽업"),  # 픽업할게 -> 피곤할게
]
# 영어로 말하거나 섞어 말하는 손님: 소문자로 바꾼 뒤 한국어로 옮기는 표
_EN_WORDS = [  # 영어로 말하거나 영어 섞어 말하는 손님: 소문자로 바꾼 뒤 한국어로 옮긴다
    (re.compile(r"\bamericano\b"), "아메리카노"), (re.compile(r"\bcaf[eé]\s*latte\b|\blatte\b"), "카페라떼"),
    (re.compile(r"\bcappuccino\b"), "카푸치노"), (re.compile(r"\bespresso\b"), "에스프레소"),
    (re.compile(r"\bvanilla\s*latte\b"), "바닐라라떼"), (re.compile(r"\bcaramel\s*macchiato\b"), "카라멜마키아토"),
    (re.compile(r"\bgrapefruit\s*ade\b"), "자몽 에이드"), (re.compile(r"\blemon\s*ade\b"), "레몬 에이드"),
    (re.compile(r"\b(?:iced|ice|cold)\b"), "아이스"), (re.compile(r"\b(?:hot|warm)\b"), "따뜻한"),
    (re.compile(r"\b(?:one|1)\b"), "한 잔"), (re.compile(r"\b(?:two|2)\b"), "두 잔"),
    (re.compile(r"\b(?:three|3)\b"), "세 잔"), (re.compile(r"\b(?:four|4)\b"), "네 잔"),
    (re.compile(r"\bplease\b|\bpls\b"), "주세요"), (re.compile(r"\bto\s*go\b|\btake\s*out\b|\btakeout\b"), "포장"),
    (re.compile(r"\bcard\b"), "카드"),
]
# '원 플리즈' 같은 영어 섞인 주문 표현 교정
_STT_PLEASE = re.compile(r"(?<![가-힣])원\s*(?=플리즈|주세요)")
_STT_PLEASE_WORD = re.compile(r"플리[즈스]")
_STT_FILLER_A = re.compile(r"(?<![가-힣])[아어음]\s+(?=아[가-힣])")  # "아 아이스…"·"아 아메리카노"의 말머리 '아'는 '아아'로 붙어 읽히므로 뺀다
_STT_AA_SPLIT = re.compile(r"(?<![가-힣])아\s+아(?![가-힣])")  # "아 아"처럼 띄어 인식된 아이스 아메리카노 줄임말


# 영어 단어가 3글자 이상 있을 때만 _EN_WORDS 로 한국어 변환
def _english_to_korean(text: str) -> str:
    if not re.search(r"[A-Za-z]{3,}", text):
        return text
    low = text.lower()
    for rx, ko in _EN_WORDS:
        low = rx.sub(ko, low)
    return low


# 같은 말이 두 번 붙어 인식된 경우를 찾는 정규식
_STT_REPEAT = re.compile(r"(?<![가-힣])((?:[가-힣]+ ){0,2}[가-힣]{2,})\s+\1(?![가-힣])")


# 인식기가 같은 말을 두 번 붙여 적은 경우('아이스 아메리카노 아이스 아메리카노 하나')를 한 번으로
def _collapse_repeats(text: str) -> str:
    """인식기가 같은 말을 두 번 붙여 적은 경우("아이스 아메리카노 아이스 아메리카노 하나")를 한 번으로."""
    def one(m):
        return m.group(1) if len(m.group(1).replace(" ", "")) >= 4 else m.group(0)
    text = re.sub(r"(?<![가-힣])(아아|뜨아|따아)(?:\s+\1)+(?![가-힣])", r"\1", text)
    return _STT_REPEAT.sub(one, text)


# 위 교정 규칙을 순서대로 적용하는 함수. 순서가 중요함: 반복 제거 → 영어→한글 → 교정표 → 말머리 '아' 제거 → 샷 교정
def fix_stt_errors(text: str) -> str:
    text = _collapse_repeats(text)
    text = apply_custom_fixes(text)  # data/stt_fixes.json 에 사용자가 추가한 보정(코드 수정 없이)
    text = _english_to_korean(text)
    text = _STT_PLEASE.sub("한 잔 ", text)
    text = _STT_PLEASE_WORD.sub("주세요", text)
    text = _STT_DECAF.sub("디카페인", text)
    text = _STT_DECAF_SHORT.sub("디카페인", text)
    text = _STT_SHOT_ADD.sub("샷 추가", text)
    text = _STT_SHOT_ADD_VERB.sub("샷 추가해", text)
    text = _STT_HOT.sub("핫으로", text)
    text = _STT_TEA_T.sub("티", text)
    text = _STT_DISCOUNT.sub("할인혜택", text)
    text = _STT_QTY2.sub("두 잔", text)
    text = _STT_AA.sub("아아 ", text)
    for rx, fixed in _STT_MENU:
        text = rx.sub(fixed, text)
    text = _STT_AA_SPLIT.sub("아아", text)
    text = _STT_FILLER_A.sub("", text)
    return _STT_SHOT.sub("샷", text)


# ──── ② 수량 추출 ────
# '샷 두 번 추가'의 숫자는 잔 수가 아니라 샷 횟수라서 수량 계산 전에 지우는 정규식
_SHOT_NUM_STRIP = re.compile(r"(?:샷|샤)\s*(?:을|를)?\s*(?:더\s*)?추가\s*(?:해서|해|로|요)?\s*(?:\d+|한|하나|두|둘|세|셋|네|넷|다섯)\s*(?:번|샷)|(?:샷|샤)\s*(?:\d+|한|하나|두|둘|세|셋|네|넷|다섯)\s*(?:개|번|잔|샷|게)?|(?:\d+|한|하나|두|둘|세|셋|네|넷|다섯)\s*(?:샷|샤)")


# '아아 하나 아니 두 잔' — 말을 고쳐 한 경우 뒤쪽 수량을 따른다
_QTY_FIX = re.compile(r"(?:아니|아냐|아니야|아니다)[\s,]*(?:[가-힣]{0,4}\s*)?((?:\d+|한|하나|두|둘|세|셋|네|넷|다섯|여섯|일곱|여덟|아홉|열)\s*(?:잔|개|게|컵))")


# 수량 추출. 순서: 샷 횟수 제거 → '아니 두 잔' 정정 → 숫자+단위 → 단어(한/두…) → 없으면 1
def extract_quantity(text: str) -> int:
    text = _SHOT_NUM_STRIP.sub(" ", text)
    fix = _QTY_FIX.search(text)
    if fix:  # "아아 하나 아니 두 잔" — 고쳐 말한 수량을 따른다
        text = fix.group(1)
    m = re.search(r"(\d+)\s*(?:잔|개|게|컵)", text)
    if m:
        return int(m.group(1))

    for word, num in sorted(QUANTITY_MAP.items(), key=lambda x: -len(x[0])):
        pattern = word + r"\s*(?:잔|개|게|컵)|(?<![가-힣])" + word + r"(?![가-힣])"
        if re.search(pattern, text):
            return num

    return 1


# 번호 선택 표현 추출용 준비물(공백 있는/없는 표기를 모두 허용하는 정규식)
_ORDINAL_KEY = {k.replace(" ", ""): k for k in ORDINAL_KEYWORDS}
_ORDINAL_RX = re.compile(
    r"(?<!\d)(?:" + "|".join(
        re.escape(k).replace("\\ ", r"\s*") for k in sorted(ORDINAL_KEYWORDS, key=len, reverse=True)) + ")")


# '2번 하나랑 3번 두 개' → [(2, ' 하나랑 '), (3, ' 두 개')] 처럼 (번호, 그 뒤에 붙은 말) 목록. 같은 번호는 한 번만
def extract_ordinal_segments(text: str) -> list[tuple[int, str]]:
    """"2번 하나랑 3번 두 개"처럼 번호를 여러 개 말했을 때 (번호, 그 번호 뒤에 붙은 말) 목록. 같은 번호는 한 번만."""
    found = [(m.start(), m.end(), ORDINAL_KEYWORDS[_ORDINAL_KEY.get(re.sub(r"\s+", "", m.group()))])
             for m in _ORDINAL_RX.finditer(text)]
    out: list[tuple[int, str]] = []
    for i, (_, end, num) in enumerate(found):
        nxt = found[i + 1][0] if i + 1 < len(found) else len(text)
        if num not in [n for n, _ in out]:
            out.append((num, text[end:nxt]))
    return out


# 사전(MENU_KEYWORDS)에서 지금 실제 메뉴판에 있는 메뉴로 연결되는 항목만 남긴다
def active_keywords(menu_names: Optional[list]) -> dict[str, str]:
    if menu_names is None:
        return MENU_KEYWORDS
    by_norm = {normalize_text(m): m for m in menu_names}
    return {k: by_norm[normalize_text(v)] for k, v in MENU_KEYWORDS.items() if normalize_text(v) in by_norm}


# 문장 안에 들어 있는 메뉴 이름 중 가장 긴 것(정식 이름 포함 검사)
def _longest_menu_in_text(text_norm: str, menu_names: list) -> Optional[str]:
    best_match, best_len = None, 0
    for name in menu_names:
        name_norm = normalize_text(name)
        if name_norm and name_norm in text_norm and len(name_norm) > best_len:
            best_match, best_len = name, len(name_norm)
    return best_match


# 반대로: 문장이 메뉴 이름의 일부일 때(예: '딸기' → '딸기 스무디') 가장 긴 메뉴
def _longest_menu_containing_text(text_norm: str, menu_names: list) -> Optional[str]:
    best_match, best_len = None, 0
    for name in menu_names:
        name_norm = normalize_text(name)
        if text_norm in name_norm and len(name_norm) > best_len:
            best_match, best_len = name, len(name_norm)
    return best_match


# '망고 스무디'처럼 여러 단어 메뉴 이름의 첫 단어와 마지막 단어만 말한 경우 후보가 1개일 때 인정
def _menu_by_split_tokens(text_norm: str, menu_names: list) -> Optional[str]:
    cands = []
    for name in menu_names:
        toks = name.split()
        if len(toks) < 2:
            continue
        first, last = normalize_text(toks[0]), normalize_text(toks[-1])
        if first in text_norm and last in text_norm:
            cands.append(name)
    return cands[0] if len(cands) == 1 else None


# 메뉴 이름 추출. 우선순위:
#  1) 메뉴판 이름이 문장에 통째로 있음(가장 긴 것)
#  2) 여러 단어 메뉴의 앞·뒤 단어만 말함
#  3) 사전(별명/줄임말)에서 찾음 — '아아', '뜨아' 등
#  4) 말한 것이 메뉴 이름의 일부임(가장 긴 메뉴)
def extract_menu(text: str, menu_names: list = None) -> Optional[str]:
    keywords = active_keywords(menu_names)
    text_norm = normalize_text(text)

    if menu_names:
        match = _longest_menu_in_text(text_norm, menu_names)
        if match:
            return match

    if menu_names:
        match = _menu_by_split_tokens(text_norm, menu_names)
        if match:
            return match

    for key in sorted(keywords.keys(), key=len, reverse=True):
        if normalize_text(key) in text_norm:
            return keywords[key]

    if menu_names:
        return _longest_menu_containing_text(text_norm, menu_names)

    return None


# OPTION_KEYWORDS 로 옵션 이름(샷추가/연하게) 목록을 뽑음(구버전)
def extract_options_from_text(text: str) -> list:
    text_norm = normalize_text(text)
    found = []
    for key, value in OPTION_KEYWORDS.items():
        if normalize_text(key) in text_norm and value not in found:
            found.append(value)
    return found


# ──── ③ 옵션 상세 추출용 정규식 ────
# 숫자 단어 표(다섯까지). [겹침] QUANTITY_MAP, _UNIT_NUM, dialog._COUNT_WORDS, cart_command._NUM_WORDS 와 같은 종류
_NUM_WORDS = NUM_WORDS_5
_NUM = r"(\d+|한|하나|두|둘|세|셋|네|넷|다섯)"

# 샷 횟수 표현 3가지('샷 두 번 추가' / '두 샷 추가' / '샷 추가 두 번')
_SHOT_COUNT_RES = [
    _rx(r"(?:샷|샤|셔츠)(?:을|를|은)?" + _NUM + r"(?:개|번|잔|샷)?(?:만)?(?:더)?(?:추가|넣|더)"),
    _rx(_NUM + r"(?:샷|샤)(?:만)?(?:더)?(?:추가|넣|더)"),
    _rx(r"(?:샷|샤|셔츠)(?:을|를)?(?:더)?추가(?:를)?(?:해서|해|로|요)?" + _NUM + r"(?:번|샷)"),  # "샷 추가 두 번"
]
# 횟수 없이 '샷 추가'만 말한 경우(1샷)
_SHOT_PLAIN_RE = _rx(r"(?:샷|샤|셔츠)(?:을|를)?(?:더)?(?:추가|넣|더)|추가샷")
_SHOT_MULTI = {"더블샷": 1, "트리플샷": 2}

# 시럽/크림 정도: 없음 / 절반 / 적게 / 많이. [겹침] dialog._LV_* 와 같은 역할
_LEVEL_NONE = _rx(r"빼|없이|넣지|제외|말고|안넣|안줘|안주")
_LEVEL_HALF = _rx(r"절반|반만|반정도|1/2|하프")
_LEVEL_LESS = _rx(r"조금|적게|살짝|약간|덜|소량")
_LEVEL_MORE = _rx(LEVEL_MORE)

# 시럽·크림 단어
_SYRUP_WORDS = ("시럽",)
_CREAM_WORDS = ("크림", "휘핑")

# 사이즈 표현(S/L/M). [겹침] dialog._SIZE_S/_SIZE_M/_SIZE_L 와 같은 역할
_SIZE_PATTERNS = [
    ("S", _rx(r"작은|작게|스몰|small|숏")),
    ("L", _rx(r"큰사이즈|큰거|큰걸|큰것|큰|크게|라지|large|벤티")),
    ("M", _rx(r"보통사이즈|중간사이즈|미디엄|레귤러|medium|톨")),
]
_SIZE_WORD_RE = _rx(r"사이즈|크기")

# 포장(가져가기) 표현 / 아래 _DINE_RE 는 매장에서 먹는 표현
_PACK_RE = _rx(r"포장|테이크아웃|가져갈|가져가|가져와|가지고\s*(?:갈|가)|들고\s*(?:갈|가)|싸줘|싸서|싸주|싸드|싸가|픽업")
_DINE_RE = _rx(r"매장|먹고갈|먹고가|드시고|여기서")


# 시럽/크림 표현의 정도를 판정(절반 → 없음 → 적게 → 많이 → 기본 '추가')
def _level_of(segment: str) -> str:
    if _LEVEL_HALF.search(segment):
        return "절반"
    if _LEVEL_NONE.search(segment):
        return "없음"
    if _LEVEL_LESS.search(segment):
        return "적게"
    if _LEVEL_MORE.search(segment):
        return "많이"
    return "추가"


# 옵션 상세 추출 → [{kind, name, count}]. 샷(개수) → 연하게 → 시럽/크림(정도, 단어 위치 기준) → 사이즈 순으로 찾는다
def extract_option_details(text: str) -> list:
    text_norm = normalize_text(text)
    details = []

    shot_count = None
    for word, n in _SHOT_MULTI.items():
        if normalize_text(word) in text_norm:
            shot_count = n
    if shot_count is None:
        for rx in _SHOT_COUNT_RES:
            m = rx.search(text_norm)
            if m:
                g = m.group(1)
                shot_count = to_int(g, _NUM_WORDS, 1)
                break
    if shot_count is None and _SHOT_PLAIN_RE.search(text_norm):
        shot_count = 1
    if shot_count is not None and shot_count >= 1:
        details.append({"kind": "shot", "name": "샷추가", "count": shot_count})

    for key in ("연하게", "약하게"):
        if normalize_text(key) in text_norm:
            details.append({"kind": "light", "name": "연하게", "count": 1})
            break

    markers = []
    for word in _SYRUP_WORDS:
        for m in re.finditer(normalize_text(word), text_norm):
            markers.append((m.start(), "syrup", "시럽"))
    for word in _CREAM_WORDS:
        for m in re.finditer(normalize_text(word), text_norm):
            markers.append((m.start(), "cream", "크림"))
    markers.sort()
    for i, (pos, kind, label) in enumerate(markers):
        if any(d["kind"] == kind for d in details):
            continue
        end = len(text_norm)
        for next_pos, next_kind, _ in markers[i + 1:]:
            if next_kind != kind:
                end = next_pos
                break
        level = _level_of(text_norm[pos:end])
        details.append({"kind": kind, "name": f"{label} {level}", "count": 1})

    if _SIZE_WORD_RE.search(text_norm) or any(rx.search(text_norm) for _, rx in _SIZE_PATTERNS[:2]):
        for size, rx in _SIZE_PATTERNS:
            if rx.search(text_norm):
                details.append({"kind": "size", "name": f"사이즈 {size}", "count": 1})
                break

    return details


# 포장이면 True, 매장이면 False, 말 안 했으면 None
def extract_packaging(text: str) -> Optional[bool]:
    text_norm = normalize_text(text)
    if _PACK_RE.search(text_norm):
        return True
    if _DINE_RE.search(text_norm):
        return False
    return None


# 속성 추출('hot'/'ice'/'sweet'…). 둘 다 나오면 '말고/아니라'로 부정된 쪽을 버린다.
# ※ 사전 키 '단'(sweet)은 한 글자라 '단호박' 같은 다른 단어에도 걸린다(실행 확인). 이 폴더에선 sweet 값을 쓰는 곳이 없어 실제 영향은 없음.
def extract_attributes(text: str):
    raw = text
    text = normalize_text(text)
    attrs = []
    for key, value in ATTRIBUTE_KEYWORDS.items():
        if normalize_text(key) in text:
            attrs.append(value)
    if "ice" not in attrs and (
        "아이스" in text or re.search(r"(?<![가-힣])(?:아아|아라|아바라|아카라)(?![가-힣])", raw)
    ):
        attrs.append("ice")
    if "ice" in attrs and "hot" in attrs:
        neg = re.search(unify_ae_e(r"말고|아니라|아닌|빼고|싫"), text)
        hot_pos = min((text.find(normalize_text(k)) for k, v in ATTRIBUTE_KEYWORDS.items()
                       if v == "hot" and normalize_text(k) in text), default=-1)
        ice_pos = min((text.find(normalize_text(k)) for k, v in ATTRIBUTE_KEYWORDS.items()
                       if v == "ice" and normalize_text(k) in text), default=-1)
        if "아이스" in text:
            ice_pos = text.find("아이스") if ice_pos < 0 else min(ice_pos, text.find("아이스"))
        if neg:
            drop = "ice" if ice_pos < hot_pos else "hot"
            attrs = [x for x in attrs if x != drop]
    return attrs


# 한 덩어리 문장 → 주문 1건 dict. 메뉴를 못 찾으면 needs_recommendation=True(추천 흐름으로).
def extract_entity(text: str, menu_names: list = None) -> Dict:
    menu = extract_menu(text, menu_names)
    attrs = extract_attributes(text)
    quantity = extract_quantity(text)
    options = extract_options_from_text(text)
    option_details = extract_option_details(text)
    packaging = extract_packaging(text)

    # 메뉴를 못 찾음 → 추천이 필요한 입력으로 반환
    if not menu:
        return {
            "menu": None,
            "attributes": attrs,
            "quantity": quantity,
            "options": options,
            "option_details": option_details,
            "packaging": packaging,
            "needs_recommendation": True,
            "matched_menu": None,
            "confidence": 0.0
        }

    # '디카페인'을 말했는데 메뉴가 일반 이름이면 '디카페인 …' 메뉴로 교체
    if menu_names and "디카페인" in text.replace(" ", "") and not menu.startswith("디카페인"):
        decaf_name = f"디카페인 {menu}"
        for name in menu_names:
            if normalize_text(name) == normalize_text(decaf_name):
                menu = name
                break

    # 온도 속성이 있으면 메뉴 이름 앞에 '아이스 '/'핫 '을 붙임(이미 붙어 있으면 생략)
    menu_norm = normalize_text(menu)
    if "ice" in attrs and not any(w in menu_norm for w in ["아이스", "ice"]):
        menu = "아이스 " + menu
    elif "hot" in attrs and not any(w in menu_norm for w in ["핫", "따뜻한", "hot"]):
        menu = "핫 " + menu

    return {
        "menu": menu,
        "attributes": attrs,
        "quantity": quantity,
        "options": options,
        "option_details": option_details,
        "packaging": packaging,
        "needs_recommendation": False,
        "matched_menu": menu,
        "confidence": 0.9 if menu_names else 0.7
    }

# 여러 메뉴를 이음말(이랑/하고/그리고/쉼표)로 나누는 정규식
MULTI_SPLIT_PATTERN = re.compile(r'\s*(?:이랑|랑|하고|그리고|과|와|,|，)\s*')


# 이음말이 없어도 문장 속 메뉴를 앞에서부터 하나씩 찾고, 각 메뉴 뒤 ~ 다음 메뉴 앞 구간에서 수량·옵션을 뽑는다.
# → [(메뉴, 수량, 옵션, 옵션상세)…]
def extract_all_menus_from_text(text: str, menu_names: list = None) -> list:
    text_norm = normalize_text(text)
    keywords = active_keywords(menu_names)

    candidates = []
    if menu_names:
        candidates += [(normalize_text(m), m) for m in menu_names]
    for v in set(keywords.values()):
        candidates.append((normalize_text(v), v))
    for k, v in keywords.items():
        norm_k = normalize_text(k)
        norm_v = normalize_text(v)
        if norm_k != norm_v:
            candidates.append((norm_k, v))

    seen = set()
    unique = []
    for norm, original in sorted(candidates, key=lambda x: -len(x[0])):
        if norm not in seen:
            seen.add(norm)
            unique.append((norm, original))

    found = []
    remaining = text_norm
    while remaining:
        best_pos = len(remaining)
        best = None
        for norm, original in unique:
            pos = remaining.find(norm)
            if 0 <= pos < best_pos:
                best_pos = pos
                best = (norm, original)
            elif best and 0 <= pos == best_pos and len(norm) > len(best[0]):
                best = (norm, original)
        if best is None:
            break
        norm, original = best

        after_menu = remaining[best_pos + len(norm):]
        next_menu_pos = len(after_menu)
        for n2, _ in unique:
            p = after_menu.find(n2)
            if 0 <= p < next_menu_pos:
                next_menu_pos = p
        qty_segment = after_menu[:next_menu_pos]
        qty = extract_quantity(qty_segment) if qty_segment else 1
        options = extract_options_from_text(qty_segment) if qty_segment else []
        details = extract_option_details(qty_segment) if qty_segment else []

        found.append((original, qty, options, details))
        remaining = remaining[:best_pos] + remaining[best_pos + len(norm):]

    return found

# '둘 다/모두/각각(씩)' — 마지막에 말한 온도를 앞 메뉴들에도 적용하라는 표현
_DISTRIBUTIVE = re.compile(normalize_text(r"씩|둘다|모두|전부|다같이") + r"|다(?=따뜻|따듯|뜨겁|뜨거|핫|아이스|차갑|차게|시원)")  # "…두 개 다 따뜻하게"


# 마지막 메뉴에만 붙은 온도('… 두 개 다 따뜻하게')를 온도 말 없는 앞 메뉴에도 공유
def _share_trailing_temperature(results: list, last_part: str) -> None:
    if len(results) < 2 or not _DISTRIBUTIVE.search(normalize_text(last_part)):
        return
    last = results[-1]
    temp = "hot" if "hot" in last["attributes"] else "ice" if "ice" in last["attributes"] else None
    if not temp:
        return
    prefix = "핫 " if temp == "hot" else "아이스 "
    for prev in results[:-1]:
        if "hot" in prev["attributes"] or "ice" in prev["attributes"]:
            continue
        prev["attributes"] = list(prev["attributes"]) + [temp]
        if prev["menu"] and not prev["menu"].startswith(("핫 ", "아이스 ")):
            prev["menu"] = prefix + prev["menu"]

# '한 잔은 … 두 잔은 …' 잔별 나눔 시작 표현. [겹침] dialog._PART, cart_command._RE_PART
_UNIT_START = re.compile(r"(?<![가-힣0-9])(\d+|한|하나|두|둘|세|셋|네|넷)\s*(?:잔|개)?\s*(?:은|는|만)(?=\s)")
_UNIT_NUM = NUM_WORDS_4


# '아메리카노 두 잔 한 잔은 연하게 한 잔은 샷 추가'처럼 잔마다 다르게 말한 주문을 잔별 주문으로 분해.
# (한 개만 나오는 '하나만 따뜻하게'는 말버릇이라 제외)
def _per_unit_orders(text: str, menu_names: Optional[list]) -> Optional[list]:
    starts = list(_UNIT_START.finditer(text))
    if not starts:
        return None
    prefix = text[:starts[0].start()]
    base = extract_entity(prefix, menu_names)
    if not base["menu"]:
        return None
    total = extract_quantity(prefix)
    if len(starts) == 1:  # "아메리카노 하나만 따뜻하게"의 '하나만'은 수량 말버릇이지 잔별 나눔이 아니다
        g1 = starts[0].group(1)
        n1 = to_int(g1, _UNIT_NUM, 1)
        if total <= n1:
            return None
    packaging = extract_packaging(text)
    out, used = [], 0
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        seg = text[m.end():end]
        g = m.group(1)
        n = to_int(g, _UNIT_NUM, 1)
        details = extract_option_details(seg)
        e = dict(base)
        e.update(quantity=n, option_details=details, options=[d["name"] for d in details], packaging=packaging)
        out.append(e)
        used += n
    rest = max(total - used, 0)
    if rest:
        e = dict(base)
        e.update(quantity=rest, packaging=packaging)
        out.append(e)
    return out


# 수량 말 + '주세요'로 끝나는 부분을 찾는 정규식(이음말 없는 여러 메뉴 주문 분리용)
_QTY_END = re.compile(
    r"(?:하나|한\s*잔|한\s*개|두\s*잔|두\s*개|세\s*잔|세\s*개|네\s*잔|네\s*개|둘|셋|\d+\s*(?:잔|개))"
    r"(?:씩|만)?(?:\s*(?:해\s*)?(?:주세요|주세여|줘요|줘|주십시오|주이소))?"
)


# '아이스 아메리카노 하나 따뜻한 라떼 하나'처럼 이음말 없이 이어 말했을 때, 수량 말 뒤에서 또 다른 메뉴가 나오면 거기서 분리
def _split_after_qty(text: str, menu_names: Optional[list]) -> list:
    """수량 말 뒤에 또 다른 메뉴가 이어지면 거기서 나눈다 (이음말 없는 여러 메뉴 주문)."""
    if not menu_names:
        return [text]
    cuts, last = [], 0
    for m in _QTY_END.finditer(text):
        e = m.end()
        if e <= last:
            continue
        rest = text[e:]
        if len(normalize_text(rest)) >= 3 and extract_menu(text[last:e], menu_names) and extract_menu(rest, menu_names):
            cuts.append(e)
            last = e
    if not cuts:
        return [text]
    bounds = [0, *cuts, len(text)]
    return [text[a:b] for a, b in zip(bounds, bounds[1:]) if text[a:b].strip()]


# 여러 메뉴 주문 분해 메인 함수. 시도 순서:
#  0) STT 오타 교정
#  1) 잔별 나눔('한 잔은… 한 잔은…') → 2) 이음말/수량 뒤 분리 → 3) 이음말 없이 메뉴 여러 개 → 4) 한 건으로 처리
# 앞 단계에서 결과가 나오면 거기서 반환한다.
def extract_multi_order(text: str, menu_names: list = None) -> list:
    text = fix_stt_errors(text)
    # [1] 잔별로 나눠 말한 경우
    per_unit = _per_unit_orders(text, menu_names)
    if per_unit:
        return per_unit
    # [2] 이음말로 나눔(없으면 수량 뒤에서 분리). 메뉴가 없는 조각은 앞 메뉴의 옵션/포장으로 합침
    parts = MULTI_SPLIT_PATTERN.split(text)
    if len(parts) == 1:  # "아이스 아메리카노 하나 따뜻한 라떼 하나"처럼 이음말 없이 이어 말한 경우
        parts = _split_after_qty(text, menu_names)
    if len(parts) > 1:
        results = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            entity = extract_entity(part, menu_names)
            if entity["menu"]:
                results.append(entity)
            elif results:
                prev = results[-1]
                have = {d["kind"] for d in prev["option_details"]}
                for d in entity["option_details"]:
                    if d["kind"] not in have:
                        prev["option_details"].append(d)
                        have.add(d["kind"])
                for name in entity["options"]:
                    if name not in prev["options"]:
                        prev["options"].append(name)
                if prev.get("packaging") is None and entity.get("packaging") is not None:
                    prev["packaging"] = entity["packaging"]
        if results:
            _share_trailing_temperature(results, parts[-1])
            return results

    # [3] 이음말 없이 메뉴가 여러 개 나온 경우(같은 메뉴 되풀이는 1건으로 취급)
    menu_qty_pairs = extract_all_menus_from_text(text, menu_names)
    if len({p[0] for p in menu_qty_pairs}) == 1 and not re.search(r"\d|[한두세네다]\s*(?:잔|개|컵)|하나|둘|셋|넷", text):
        menu_qty_pairs = menu_qty_pairs[:1]  # "캐모마일 있죠 캐모마일"처럼 같은 메뉴를 되풀이해 말한 것
    if len(menu_qty_pairs) > 1:
        attrs = extract_attributes(text)
        results = []
        packaging = extract_packaging(text)
        for menu, qty, options, details in menu_qty_pairs:
            results.append({
                "menu": menu,
                "attributes": attrs,
                "quantity": qty,
                "options": options,
                "option_details": details,
                "packaging": packaging,
                "needs_recommendation": False,
                "matched_menu": menu,
                "confidence": 0.7,
            })
        return results

    # [4] 위에 해당 안 되면 문장 전체를 주문 1건으로
    return [extract_entity(text, menu_names)]
