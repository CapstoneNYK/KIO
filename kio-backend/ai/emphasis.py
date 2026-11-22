# [emphasis.py] 화면에 보이는 안내 문구에서 중요한 단어(메뉴·수량·옵션·금액·결제수단·포장/매장·온도)를 **굵게** 표시한다.
#  프론트의 말풍선이 **…** 를 굵은 글씨로 그리고, 음성(TTS)은 별표를 읽지 않고 걸러 낸다.
#  이미 **…** 로 감싼 부분은 건드리지 않고, '1번 메뉴' 같은 번호 목록 줄은 그대로 둔다.
import re

from ai.korean import normalize_text  # noqa: F401  (다른 모듈과 같은 import 규칙 유지)
from ai.payment import _METHOD_LABELS, _SHORT_LABELS

_QTY = r"(?:\d+|한|두|세|네|다섯)\s?(?:잔|개)"
_BOLD = re.compile(r"\*\*.+?\*\*")
_NUMBERED = re.compile(r"^\s*\d+\s*(?:번|\.)\s*\S")
# 메뉴 이름이 아닌 고정 표현: 금액 / 따뜻하게·차갑게 / 포장·매장 / 따옴표 속 옵션 이름 / 품절
_FIXED = re.compile(
    r"\d[\d,]*원"
    r"|'[^'\n]{1,12}'"
    r"|따뜻하게|차갑게"
    r"|먹고\s?가기|가져\s?가기|포장|매장"
    r"|품절"
)


# 답변 속 용어 표기 바로잡기: LLM 이 가끔 'T멤bership'처럼 영문을 섞거나 '티멤버십'이라고 쓴다 → 'T멤버십'
_MEMBERSHIP_LATIN = re.compile(r"(?i)멤\s*bership|membership")
_TMEMBERSHIP = re.compile(r"(?<![가-힣A-Za-z])(?:T|t|티)\s*멤버십")


def clean_terms(answer: str) -> str:
    if not answer:
        return answer
    out = _MEMBERSHIP_LATIN.sub("멤버십", answer)
    return _TMEMBERSHIP.sub("T멤버십", out)


def _method_names() -> list[str]:
    names = set(_METHOD_LABELS.values()) | set(_SHORT_LABELS.values())
    return sorted(names, key=len, reverse=True)


def emphasize(answer: str, menu_names: list[str]) -> str:
    """answer 안의 중요한 단어를 **…** 로 감싼 문장을 돌려준다(이미 굵은 부분·번호 목록 줄은 그대로)."""
    if not answer:
        return answer
    names = sorted({n for n in menu_names if n}, key=len, reverse=True)
    parts = [
        # 온도 말머리 + 메뉴 이름 + (수량): "아이스 아메리카노 2잔"
        r"(?:(?:아이스|따뜻한|핫)\s)?(?:" + "|".join(re.escape(n) for n in names) + r")(?:\s" + _QTY + r")?" if names else None,
        "|".join(re.escape(m) for m in _method_names()),
        _FIXED.pattern,
    ]
    pattern = re.compile("|".join(p for p in parts if p))

    def bold_plain(text: str) -> str:
        def wrap(m: re.Match) -> str:
            s = m.group(0)
            if s.startswith("'") and s.endswith("'"):
                s = s[1:-1]  # '샷추가' → **샷추가**
            return f"**{s}**"
        return pattern.sub(wrap, text)

    out_lines = []
    for line in answer.split("\n"):
        if _NUMBERED.match(line):
            out_lines.append(line)
            continue
        pieces, last = [], 0
        for m in _BOLD.finditer(line):  # 이미 굵은 부분은 건너뛴다
            pieces.append(bold_plain(line[last:m.start()]))
            pieces.append(m.group(0))
            last = m.end()
        pieces.append(bold_plain(line[last:]))
        out_lines.append("".join(pieces))
    return "\n".join(out_lines).replace("****", "")
