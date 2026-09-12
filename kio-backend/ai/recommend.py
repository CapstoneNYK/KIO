import json
import re

from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from ai.dictionary import MENU_DICTIONARY
from ai.llm import get_llm
from app.ocr.db import get_all_menu_texts, get_all_discount_texts

load_dotenv()

# 유료 OpenAI API 대신 자체 호스팅(Ollama) LLM 사용
_qa_llm = get_llm(temperature=0)


def _normalize_with_dictionary(question: str) -> str:
    """질문을 사전(MENU_DICTIONARY) 기준으로 표준화한다.

    기존에는 이 단순 치환 작업에도 GPT를 한 번 더 호출했는데, 규칙 기반
    문자열 치환만으로 충분한 작업이라 LLM 호출 없이 처리하도록 바꿨다.
    (지연시간 감소 + 항상 일관된 결과)
    """
    normalized = question
    for key in sorted(MENU_DICTIONARY.keys(), key=len, reverse=True):
        if key in normalized:
            normalized = normalized.replace(key, MENU_DICTIONARY[key])
    return normalized


def _build_menu_context() -> str:
    menus = get_all_menu_texts()
    if not menus:
        return "현재 등록된 메뉴가 없습니다."
    return "\n".join(f"- {m}" for m in menus)


_POSTER_LABEL = {
    "poster_kt": "KT 멤버십",
    "poster_t": "T 멤버십 (SKT 계열)",
    "poster_tpass": "T우주패스 (SKT 계열)",
}

def _build_discount_context() -> str:
    grouped = get_all_discount_texts()
    if not grouped:
        return "등록된 할인 정보가 없습니다."
    sections: list[str] = []
    for screen_name, texts in sorted(grouped.items()):
        label = _POSTER_LABEL.get(screen_name, screen_name)
        body = "\n".join(f"  - {t}" for t in texts)
        sections.append(f"[{label}]\n{body}")
    return "\n\n".join(sections)


# ── QA 체인 (OCR DB 기반) ────────────────────────────────────────────────────

_qa_prompt = ChatPromptTemplate.from_template("""
당신은 카페 키오스크 안내 전문가입니다.
아래 메뉴 목록과 할인 혜택 정보를 바탕으로 질문에 답변해주세요.

주의: 할인 혜택 정보는 포스터 이미지를 OCR로 추출한 텍스트라 오타나 깨진 글자가 있을 수 있습니다.
예를 들어 "멈버십"은 "멤버십", "3096"은 "30%", "5096"은 "50%", "스랜"은 "스캔"을 의미합니다.
오타가 있더라도 최대한 해석하여 답변해주세요.
정보가 전혀 없을 때만 "해당 정보를 알 수 없습니다."라고 답하세요.
T멤버십과 T우주패스는 모두 SKT 계열사입니다. "SKT 할인"처럼 SKT를 언급하는 질문에는 두 가지 혜택을 모두 간단히 안내하세요.
할인 적용 가능 여부를 묻는 질문이라면, 현재 장바구니 메뉴와 대조하여 할인 대상 여부를 명확히 안내하세요.
T멤버십 할인은 아메리카노(핫/아이스 온도 무관)에 적용됩니다. 장바구니에 아메리카노가 있다면 할인 가능합니다.
답변은 간결하게 해주세요.

메뉴 목록:
{menu_context}

할인 혜택 정보:
{discount_context}

현재 장바구니:
{cart_context}

질문: {question}
답변:
""")

def _build_cart_context(cart_items: list[str]) -> str:
    if not cart_items:
        return "장바구니가 비어 있습니다."
    return "\n".join(f"- {item}" for item in cart_items)


qa_chain = (
    {
        "question": RunnableLambda(lambda x: _normalize_with_dictionary(x["question"]) if isinstance(x, dict) else _normalize_with_dictionary(x)),
        "menu_context": RunnableLambda(lambda _: _build_menu_context()),
        "discount_context": RunnableLambda(lambda _: _build_discount_context()),
        "cart_context": RunnableLambda(lambda x: _build_cart_context(x.get("cart_items", [])) if isinstance(x, dict) else "장바구니가 비어 있습니다."),
    }
    | _qa_prompt
    | _qa_llm
    | StrOutputParser()
)


# ── 추천 체인 (OCR DB + 자체 호스팅 LLM, JSON 파싱) ──────────────────────────

class RecommendOutput(BaseModel):
    answer: str        # 손님에게 보여줄 추천 메시지
    menus: list[str]   # 추천 메뉴명 목록 (OCR DB에 있는 이름 그대로)


_recommend_prompt = ChatPromptTemplate.from_template("""
당신은 카페 키오스크 음료 추천 전문가입니다.
아래는 현재 주문 가능한 메뉴 목록입니다.

{menus}

손님 요청: {question}

위 메뉴 목록에서만 골라 손님의 취향에 맞는 음료를 1~2가지 추천해 주세요.
각 메뉴가 왜 어울리는지 맛 특징을 한 줄로 설명해 주세요.
목록에 없는 메뉴는 절대 추천하지 마세요.
메뉴 목록이 비어 있거나 요청에 맞는 메뉴가 없으면, answer에 "죄송합니다, 현재 해당 조건에 맞는 메뉴를 찾을 수 없습니다."라고 적고 menus는 빈 목록으로 응답하세요.

반드시 아래 JSON 형식으로만 응답하세요. 다른 설명이나 코드블록 표시 없이 JSON만 출력하세요:
{{
  "answer": "1. 메뉴명 - 맛 설명\\n2. 메뉴명 - 맛 설명",
  "menus": ["메뉴명1", "메뉴명2"]
}}
""")

# 유료 OpenAI API 대신 자체 호스팅(Ollama) LLM 사용.
# 로컬 모델은 GPT-4o의 structured output(with_structured_output)만큼 형식을
# 안정적으로 지키지 않을 수 있어, 프롬프트로 JSON 형식을 지시하고 아래에서
# 직접 파싱한 뒤 실패 시 안전하게 폴백한다.
_recommend_llm = get_llm(temperature=0.7)

_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _parse_recommend_output(raw: str) -> RecommendOutput:
    match = _JSON_BLOCK_PATTERN.search(raw)
    if match:
        try:
            data = json.loads(match.group(0))
            return RecommendOutput(
                answer=data.get("answer", raw.strip()),
                menus=data.get("menus", []),
            )
        except (json.JSONDecodeError, TypeError):
            pass
    # JSON 파싱 실패 시에도 서비스가 죽지 않도록 원문 텍스트를 그대로 답변으로 사용
    return RecommendOutput(answer=raw.strip(), menus=[])


recommend_chain = (
    {
        "question": RunnablePassthrough(),
        "menus": RunnableLambda(lambda _: _build_menu_context()),
    }
    | _recommend_prompt
    | _recommend_llm
    | StrOutputParser()
    | RunnableLambda(_parse_recommend_output)
)
