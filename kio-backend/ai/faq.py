# [faq.py] 관리자가 등록한 자주 묻는 질문(화장실·와이파이·영업시간…)에 LLM 없이 바로 답한다.
# 키워드 규칙: 쉼표(,)로 나눈 것 중 하나라도 말에 들어 있으면 해당 FAQ. '+' 로 묶으면 전부 들어 있어야 한다(예: "와이파이+비번, 와이파이+비밀번호").
import re

from ai import data_source
from ai.korean import normalize_text


# 공백을 없앤 정규화 문자열(띄어쓰기가 달라도 맞게)
def _squash(text: str) -> str:
    return re.sub(r"\s+", "", normalize_text(text))


# 한 FAQ 가 질문에 얼마나 잘 맞는지(맞은 키워드 글자 수 합). 안 맞으면 0
def _score(query: str, keywords: str) -> int:
    best = 0
    for alt in re.split(r"[,，、\n]", keywords or ""):
        parts = [_squash(p) for p in alt.split("+") if p.strip()]
        if parts and all(p in query for p in parts):
            best = max(best, sum(len(p) for p in parts))
    return best


def faq_answer(query: str, faqs: list[dict] | None = None) -> str | None:
    """등록된 FAQ 중 가장 잘 맞는 답을 돌려준다(없으면 None)."""
    faqs = faqs if faqs is not None else data_source.get_faqs(active_only=True)
    q = _squash(query)
    scored = [(_score(q, f.get("keywords", "")), f) for f in faqs if f.get("answer")]
    scored = [(s, f) for s, f in scored if s > 0]
    if not scored:
        return None
    return max(scored, key=lambda x: x[0])[1]["answer"].strip()
