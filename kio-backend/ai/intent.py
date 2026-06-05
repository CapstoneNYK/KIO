import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

load_dotenv()

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0 
)

# 의도 종류
INTENTS = ["recommend", "qa", "order", "coupon", "payment"]

# 의도 분류 프롬프트
intent_prompt = ChatPromptTemplate.from_template("""
당신은 카페 키오스크 음성 주문 시스템의 AI입니다.

사용자의 입력을 아래 4가지 의도 중 하나로 분류하세요.

1. recommend → 메뉴 추천 요청
   - 예: "당 떨어지는데 음료 추천해줘", "달달한 거 뭐 있어?"

2. qa → 메뉴 정보 질문
   - 예: "아메리카노 얼마야?", "카페라떼 칼로리 뭐야?"

3. order → 주문 또는 행동 요청
   - 예: "아메리카노 하나 줘", "라떼 주문할게", "이거 담아줘"

4. coupon → 쿠폰/상품권 사용 요청 또는 질문
   - 예: "이 쿠폰 어떻게 써?", "쿠폰 사용하고 싶어", "상품권 쓰는 방법 알려줘", "이거 쿠폰인데 어떻게 해?"

5. payment → 결제 또는 주문 확정 요청
   - 예: "결제할게", "주문할게요", "이거로 할게", "결제해줘", "주문 완료", "계산해줘"


규칙:
- 반드시 아래 넷 중 하나만 출력하세요
- 다른 말 절대 하지 마세요

출력:
recommend / qa / order / coupon / payment

사용자 입력: {question}
""")

# 의도 분류 체인
intent_chain = (
    intent_prompt
    | llm
    | StrOutputParser()
)

# 의도 분류 함수
def classify_intent(question: str) -> str:
    try:
        result = intent_chain.invoke({"question": question})
        intent = result.strip().lower()

        if intent not in INTENTS:
            return "qa"

        return intent

    except Exception as e:
        print("Intent 분류 오류:", e)
        return "qa"


# 실행 테스트
if __name__ == "__main__":
    test_inputs = [
        "당 떨어지는데 음료 추천해줘",
        "아메리카노 얼마야?",
        "아메리카노 하나 줘",
        "라떼 주문할게",
        "달달한 거 뭐 있음?"
    ]

    for q in test_inputs:
        print(f"\n입력: {q}")
        print("intent:", classify_intent(q))