from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from ai.dictionary import MENU_DICTIONARY
from app.ocr.db import get_all_menu_texts

load_dotenv()

_qa_llm = ChatOpenAI(model="gpt-4o", temperature=0)

_dictionary_text = "\n".join(f"{k} → {v}" for k, v in MENU_DICTIONARY.items())

_dict_prompt = ChatPromptTemplate.from_template("""
사용자의 질문을 보고, 아래 사전을 참고해 질문을 표준화하세요.
변경할 필요가 없다면 질문을 그대로 반환하세요.

사전: {dictionary}
질문: {question}
""")

_dict_chain = (
    {"question": RunnablePassthrough(), "dictionary": RunnableLambda(lambda _: _dictionary_text)}
    | _dict_prompt
    | _qa_llm
    | StrOutputParser()
)


def _build_menu_context() -> str:
    menus = get_all_menu_texts()
    if not menus:
        return "현재 등록된 메뉴가 없습니다."
    return "\n".join(f"- {m}" for m in menus)


# ── QA 체인 (OCR DB 기반) ────────────────────────────────────────────────────

_qa_prompt = ChatPromptTemplate.from_template("""
당신은 카페 메뉴 추천 전문가입니다.
아래는 현재 주문 가능한 메뉴 목록입니다. 이 목록을 바탕으로 질문에 답변해주세요.
목록에 없는 내용은 절대 추측하지 말고, "해당 정보를 알 수 없습니다."라고 답해주세요.
답변은 간결하게 해주세요.

메뉴 목록: {context}
질문: {question}
답변:
""")

qa_chain = (
    {
        "question": _dict_chain,
        "context": RunnableLambda(lambda _: _build_menu_context()),
    }
    | _qa_prompt
    | _qa_llm
    | StrOutputParser()
)


# ── 추천 체인 (OCR DB + GPT, 구조화 출력) ────────────────────────────────────

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

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "answer": "1. 메뉴명 - 맛 설명\\n2. 메뉴명 - 맛 설명",
  "menus": ["메뉴명1", "메뉴명2"]
}}
""")

_recommend_llm = ChatOpenAI(model="gpt-4o", temperature=0.7).with_structured_output(RecommendOutput)

recommend_chain = (
    {
        "question": RunnablePassthrough(),
        "menus": RunnableLambda(lambda _: _build_menu_context()),
    }
    | _recommend_prompt
    | _recommend_llm
)
