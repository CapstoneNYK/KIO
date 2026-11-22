# [stt_fixes.py] 코드를 고치지 않고 음성인식 오류를 보정하는 사용자 표(data/stt_fixes.json).
#   형식: {"틀리게 들린 말": "올바른 말", ...}   예) {"셔츠 갈아": "샷 추가해"}
#   파일을 저장하면 서버를 다시 켜지 않아도 다음 요청부터 적용된다. 띄어쓰기가 달라도 맞는다(글자 사이 공백 허용).
#   추가는 `python -m tools.stt_report --add "틀린말=올바른말"` 로 하면 검사까지 해 준다.
import json
import os
import re

from ai.logging_utils import DATA_DIR

FIXES_PATH = os.path.join(DATA_DIR, "stt_fixes.json")
MIN_WRONG_LEN = 2  # 한 글자 교정은 멀쩡한 말까지 바꿀 수 있어 받지 않는다

_cache: dict = {"mtime": None, "rules": []}


# 틀린 말 → 글자 사이에 공백이 있어도 맞는 정규식
def _pattern(wrong: str) -> re.Pattern:
    chars = [re.escape(c) for c in wrong if not c.isspace()]
    return re.compile(r"(?<![가-힣])" + r"\s*".join(chars))


# 파일이 바뀌었을 때만 다시 읽어 (정규식, 올바른 말) 목록을 만든다. 깨진 파일은 무시한다
def _rules() -> list:
    try:
        mtime = os.path.getmtime(FIXES_PATH)
    except OSError:
        _cache.update(mtime=None, rules=[])
        return []
    if _cache["mtime"] == mtime:
        return _cache["rules"]
    rules = []
    try:
        with open(FIXES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for wrong, right in sorted(data.items(), key=lambda kv: -len(kv[0])):  # 긴 것부터 적용
            if isinstance(wrong, str) and isinstance(right, str) and len(wrong.replace(" ", "")) >= MIN_WRONG_LEN:
                rules.append((_pattern(wrong), right))
    except Exception as e:
        print("stt_fixes.json 읽기 실패:", e)
    _cache.update(mtime=mtime, rules=rules)
    return rules


def apply_custom_fixes(text: str) -> str:
    for rx, right in _rules():
        text = rx.sub(right, text)
    return text
