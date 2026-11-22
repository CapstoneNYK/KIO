"""한글 처리 공용 도구 (여러 파일에 복사돼 있던 것을 한곳으로 모음).

- normalize_text : 비교용 정규화(소문자 + 공백 제거 + ㅐ/ㅔ 통일). 프로젝트 모든 정규식 비교의 기준
- rx             : 패턴도 같은 방식으로 정규화해서 컴파일 (옛 이름 _rx 로도 각 파일에서 쓴다)
- has_final      : 마지막 글자에 받침이 있는지
- NUM_WORDS 등   : 숫자 단어 → 정수 표

주의: 비교 대상 텍스트가 normalize_text 를 거치면 'ㅐ'가 모두 'ㅔ'가 된다.
      그래서 정규식 패턴은 반드시 rx() 로 컴파일해야 한다(그냥 re.compile 에 'ㅐ' 글자를 쓰면 영원히 안 맞는다).
"""
import re


# 한글 'ㅐ'와 'ㅔ'를 같은 글자로 통일(발음이 같아서 STT 가 자주 헷갈림). 예: 에이드/애이드
def _unify_ae_e(ch: str) -> str:
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        offset = code - 0xAC00
        initial = offset // (21 * 28)
        medial = (offset % (21 * 28)) // 28
        final = offset % 28
        if medial == 1:
            medial = 5
        elif medial == 3:
            medial = 7
        return chr(0xAC00 + (initial * 21 + medial) * 28 + final)
    return ch


# 비교용 정규화: 소문자 + 공백 전부 제거 + ㅐ/ㅔ 통일. 프로젝트 모든 정규식 비교의 기준이다.
def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", "", text)
    text = "".join(_unify_ae_e(ch) for ch in text)
    return text


# 패턴 문자열의 ㅐ/ㅔ 만 통일 (소문자화·공백제거는 안 함 → \S, \s 같은 정규식 기호가 안 망가진다)
def unify_ae_e(text: str) -> str:
    return "".join(_unify_ae_e(ch) for ch in text)


# 이미 normalize_text 를 거친 문장에 쓰는 정규식 중 \s/\S 등을 써서 rx() 를 못 쓰는 경우 이걸로 컴파일
def rx_keep(pattern: str) -> "re.Pattern":
    return re.compile(unify_ae_e(pattern))


# 정규식 컴파일 헬퍼: 패턴을 normalize_text 로 맞춘 뒤 컴파일
def rx(pattern: str) -> "re.Pattern":
    return re.compile(normalize_text(pattern))


# 한글 마지막 글자에 받침이 있는지 (을/를, 은/는 선택용)
def has_final(word: str) -> bool:
    ch = word[-1]
    code = ord(ch)
    return 0xAC00 <= code <= 0xD7A3 and (code - 0xAC00) % 28 != 0


# 숫자 단어 → 정수 표. 파일마다 인식 범위가 달라서(넷까지 / 다섯까지 / 열까지) 범위별로 이름을 나눠 둔다.
# 순서를 바꾸면 안 된다(entity.extract_quantity 가 길이순 정렬 후 같은 길이끼리는 이 순서를 따른다).
NUM_WORDS_10 = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4,
                "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10}
NUM_WORDS_5 = {w: n for w, n in NUM_WORDS_10.items() if n <= 5}   # 다섯까지
NUM_WORDS_4 = {w: n for w, n in NUM_WORDS_10.items() if n <= 4}   # 넷까지


# 정규식으로 잡은 숫자 조각(g)을 정수로: 숫자면 그대로, 단어면 table 에서 찾고 없으면 default
def to_int(g: str, table: dict, default: int = 1) -> int:
    return int(g) if g.isdigit() else table.get(g, default)
