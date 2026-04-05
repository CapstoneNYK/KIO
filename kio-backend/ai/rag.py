import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings,ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda ,RunnablePassthrough
from langchain_pinecone import PineconeVectorStore
from dictionary import MENU_DICTIONARY

load_dotenv()
dictionary = MENU_DICTIONARY

# 임베딩 모델 (의미 기반 검색용)
embedding = OpenAIEmbeddings(model="text-embedding-3-small")

# LLM 모델 
llm = ChatOpenAI(model='gpt-4o')

# 벡터 DB 연결
vectorstore = PineconeVectorStore(
    index_name="cafe-menu-index",
    embedding=embedding
)

# RAG (유사한 메뉴 5개 검색)
retriever = vectorstore.as_retriever(search_kwargs={'k': 5})

# LLM이 읽기 쉬운 문자열로 변환
def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

# LLM 프롬프트에 넣기 좋은 형태로 변환
dictionary_text = "\n".join(
    [f"{k} → {v}" for k, v in dictionary.items()]
)

# 질문 표준화 체인
dictionary_prompt = ChatPromptTemplate.from_template("""
    사용자의 질문을 보고, 아래 사전을 참고해 질문을 표준화하세요.
    변경할 필요가 없다면 질문을 그대로 반환하세요.

    사전: {dictionary}
    
    질문: {question}
""")

# 질문 표준화 체인 (사전 기반)
dictionary_chain = (
    {
        "question": RunnablePassthrough(),
        "dictionary": RunnableLambda(lambda _: dictionary_text)
    }
    | dictionary_prompt
    | llm
    | StrOutputParser()
)

# 최종 QA 체인 (사전 기반 질문 표준화 + RAG)
qa_prompt = ChatPromptTemplate.from_template("""
당신은 카페 메뉴 추천 전문가입니다.
아래 검색된 메뉴 정보를 바탕으로 질문에 답변해주세요.
모르는 경우 모른다고 말하고, 답변은 간결하게 해주세요.

질문: {question}
검색된 메뉴 정보: {context}
답변:
""")

# 최종 QA 체인
qa_chain = (
    {
        "question": dictionary_chain,
        "context": dictionary_chain | retriever | format_docs
    }
    | qa_prompt
    | llm
    | StrOutputParser()
)

# 실행
if __name__ == "__main__":
    query = "커피베이 아아 있어?"
    answer = qa_chain.invoke(query)
    print("질문:", query)
    print("답변:", answer)