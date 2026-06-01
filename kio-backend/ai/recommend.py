from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_pinecone import PineconeVectorStore
from ai.dictionary import MENU_DICTIONARY
from app.ocr.db import get_all_menu_texts

load_dotenv()

llm = ChatOpenAI(model="gpt-4o", temperature=0.7)


# ── QA 체인 (Pinecone RAG) ───────────────────────────────────────────────────

_qa_llm = ChatOpenAI(model="gpt-4o", temperature=0)
embedding = OpenAIEmbeddings(model="text-embedding-3-small")
vectorstore = PineconeVectorStore(index_name="cafe-menu-index", embedding=embedding)
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

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

_qa_prompt = ChatPromptTemplate.from_template("""
당신은 카페 메뉴 추천 전문가입니다.
아래 검색된 메뉴 정보를 바탕으로 질문에 답변해주세요.
모르는 경우 모른다고 말하고, 답변은 간결하게 해주세요.

질문: {question}
검색된 메뉴 정보: {context}
답변:
""")

qa_chain = (
    {
        "question": _dict_chain,
        "context": _dict_chain | retriever | (lambda docs: "\n\n".join(d.page_content for d in docs)),
    }
    | _qa_prompt
    | _qa_llm
    | StrOutputParser()
)


# ── 추천 체인 (OCR DB + GPT) ─────────────────────────────────────────────────

def _build_menu_context() -> str:
    menus = get_all_menu_texts()
    if not menus:
        return "현재 등록된 메뉴가 없습니다."
    return "\n".join(f"- {m}" for m in menus)


_recommend_prompt = ChatPromptTemplate.from_template("""
당신은 카페 키오스크 음료 추천 전문가입니다.
아래는 현재 주문 가능한 메뉴 목록입니다.

{menus}

손님 요청: {question}

위 메뉴 목록에서만 골라 손님의 취향에 맞는 음료를 1~2가지 추천해 주세요.
각 메뉴가 왜 어울리는지 맛 특징을 한 줄로 설명해 주세요.
목록에 없는 메뉴는 절대 추천하지 마세요.
""")

recommend_chain = (
    {
        "question": RunnablePassthrough(),
        "menus": RunnableLambda(lambda _: _build_menu_context()),
    }
    | _recommend_prompt
    | llm
    | StrOutputParser()
)
