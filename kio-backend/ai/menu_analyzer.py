# [menu_analyzer.py] 메뉴를 등록할 때 맛 태그와 카페인 여부를 자동으로 정한다(규칙 + LLM 조합).
import json
import re
from typing import Callable, Optional

# 허용하는 맛 태그 12개. [겹침] preference._TAG_PATTERNS 가 같은 12개를 쓴다(둘이 어긋나면 추천에서 태그가 안 맞음).
ALLOWED_TAGS = ["산미", "상큼", "달콤", "고소", "쌉쌀", "진한", "부드러운", "향긋", "과일", "탄산", "깔끔", "상쾌"]
# 메뉴당 최대 태그 수
MAX_TAGS = 4

# LLM 이 태그를 못 정했을 때 쓰는 카테고리별 기본 태그
CATEGORY_DEFAULT_TAGS = {
    "커피": ["쌉쌀", "고소"],
    "디카페인": ["고소", "부드러운"],
    "논커피": ["달콤", "부드러운"],
    "스무디": ["달콤", "과일"],
    "에이드": ["상큼", "탄산"],
    "주스": ["상큼", "과일"],
    "티": ["향긋", "깔끔"],
}

# 카페인 없는 차 이름 단어(허브·캐모마일·페퍼민트 …)
_CAFFEINE_FREE_TEA = re.compile(r"허브|캐모마일|카모마일|페퍼민트|민트|유자|자몽|레몬|보리|호지|루이보스|생강|대추|오미자|히비스커스|매실")


# 규칙으로 카페인 여부 결정: 디카페인 → False / 에이드·주스·스무디·논커피(커피·초코 등이 이름에 있으면 불확실) / 커피 → True / 티는 이름으로 판단. 못 정하면 None
def decide_caffeine(name: str, category: str) -> Optional[bool]:
    if "디카페인" in name or category == "디카페인":
        return False
    if re.search(r"버블티|밀크티", name):  # 홍차 기반이라 카페인이 있다
        return True
    if category in ("에이드", "주스", "스무디", "논커피"):
        return False if not re.search(r"커피|모카|말차|녹차|초코", name) else None
    if category == "커피":
        return True
    if category == "티":
        if _CAFFEINE_FREE_TEA.search(name):
            return False
        if re.search(r"얼그레이|홍차|녹차|말차|블랙티|우롱|밀크티|아이스티", name):
            return True
        return None
    return None


# LLM 에 보내는 분석 프롬프트(허용 태그 중에서만 고르고 JSON 만 출력)
def _prompt(name: str, category: str, description: str) -> str:
    return (
        "카페 메뉴의 맛 특징을 분석하세요.\n"
        f"메뉴명: {name}\n카테고리: {category}\n설명: {description or '(없음)'}\n\n"
        f"맛 태그는 반드시 다음 중에서만 1~{MAX_TAGS}개 고르세요: {', '.join(ALLOWED_TAGS)}\n"
        "카페인이 들어 있으면 caffeine을 true, 없으면 false로 하세요.\n"
        "다른 설명이나 코드블록 없이 아래 JSON만 출력하세요:\n"
        '{"tags": ["태그1", "태그2"], "caffeine": true}'
    )


# LLM 응답에서 JSON dict 를 꺼냄(실패 시 None). [겹침] recommend._parse_recommend_output 와 같은 방식의 JSON 추출
def _parse(raw: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


# 기본 LLM 호출 함수(테스트에서는 llm_call 로 교체 가능)
def _default_llm_call(prompt: str) -> str:
    from ai.llm import get_llm
    res = get_llm(temperature=0).invoke(prompt)
    return getattr(res, "content", str(res))


# 메뉴 분석 메인 함수: ① 규칙으로 카페인 결정 ② LLM 으로 태그·카페인 추출
# 태그가 비면 카테고리 기본 태그 사용 / 카페인은 규칙 결과 > LLM 결과 > 기본 True 순으로 우선
def analyze_menu(
    name: str,
    category: str,
    description: str = "",
    llm_call: Optional[Callable[[str], str]] = None,
) -> dict:
    # 규칙 기반 결과를 먼저 계산
    rule_caffeine = decide_caffeine(name, category)
    tags: list = []
    llm_caffeine: Optional[bool] = None
    source = "rule"
    try:
        raw = (llm_call or _default_llm_call)(_prompt(name, category, description))
        data = _parse(raw) or {}
        tags = [t for t in data.get("tags", []) if t in ALLOWED_TAGS]
        tags = list(dict.fromkeys(tags))[:MAX_TAGS]
        if isinstance(data.get("caffeine"), bool):
            llm_caffeine = data["caffeine"]
        if tags:
            source = "llm"
    except Exception:
        tags = []
    # LLM 이 유효한 태그를 못 줬으면 카테고리 기본 태그로
    if not tags:
        tags = list(CATEGORY_DEFAULT_TAGS.get(category, []))
    # 카페인 우선순위: 규칙 → LLM → 기본값(True)
    if rule_caffeine is not None:
        caffeine = rule_caffeine
    elif llm_caffeine is not None:
        caffeine = llm_caffeine
    else:
        caffeine = True
    return {"tags": tags, "caffeine": caffeine, "source": source}
