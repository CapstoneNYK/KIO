from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from ai.dictionary import MENU_DICTIONARY
# from app.ocr.db import get_all_menu_texts, get_all_discount_texts
from app.admin import db as admin_db

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


# def _build_menu_context() -> str:
#     menus = get_all_menu_texts()
#     if not menus:
#         return "현재 등록된 메뉴가 없습니다."
#     return "\n".join(f"- {m}" for m in menus)
def _build_menu_context() -> str:
    menus = admin_db.get_menus()
    if not menus:
        return "현재 등록된 메뉴가 없습니다."
    return "\n".join(
        f"- {m['name']} ({m['price']}원, {m['category']}){' [품절]' if m['sold_out'] else ''}"
        for m in menus
    )




# _POSTER_LABEL = {
#     "poster_kt": "KT 멤버십",
#     "poster_t": "T 멤버십 (SKT 계열)",
#     "poster_tpass": "T우주패스 (SKT 계열)",
# }

# def _build_discount_context() -> str:
#     grouped = get_all_discount_texts()
#     if not grouped:
#         return "등록된 할인 정보가 없습니다."
#     sections: list[str] = []
#     for screen_name, texts in sorted(grouped.items()):
#         label = _POSTER_LABEL.get(screen_name, screen_name)
#         body = "\n".join(f"  - {t}" for t in texts)
#         sections.append(f"[{label}]\n{body}")
#     return "\n\n".join(sections)
def _build_discount_context() -> str:
    discounts = admin_db.get_discounts(active_only=True)
    if not discounts:
        return "등록된 할인 정보가 없습니다."
    sections = []
    for d in discounts:
        method_label = admin_db.DISCOUNT_METHODS.get(d["method_code"], d["method_code"])
        sections.append(f"[{d['name']} - {method_label}]\n{d['description']}")
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
        "question": RunnableLambda(lambda x: _dict_chain.invoke(x["question"]) if isinstance(x, dict) else _dict_chain.invoke(x)),
        "menu_context": RunnableLambda(lambda _: _build_menu_context()),
        "discount_context": RunnableLambda(lambda _: _build_discount_context()),
        "cart_context": RunnableLambda(lambda x: _build_cart_context(x.get("cart_items", [])) if isinstance(x, dict) else "장바구니가 비어 있습니다."),
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
