from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ai.llm import get_llm, OLLAMA_INTENT_MODEL

load_dotenv()

# 유료 OpenAI API 대신 자체 호스팅(Ollama) LLM 사용.
# 의도 분류는 6지선다 단순 작업이라 무거운 기본 모델 대신 가벼운 전용 모델을
# 쓸 수 있게 분리(OLLAMA_INTENT_MODEL 미설정 시 기본 모델과 동일).
llm = get_llm(temperature=0, model=OLLAMA_INTENT_MODEL)

# 의도 종류
INTENTS = ["recommend", "qa", "order", "coupon", "payment", "order_and_pay"]

# 의도 분류 프롬프트
intent_prompt = ChatPromptTemplate.from_template("""
당신은 카페 키오스크 음성 주문 시스템의 AI입니다.

사용자의 입력을 아래 6가지 의도 중 하나로 분류하세요.

1. recommend → 메뉴 추천 요청
   - 예: "당 떨어지는데 음료 추천해줘", "달달한 거 뭐 있어?"
   - 주의: 문장이 잡음/오인식처럼 불분명하거나 무슨 의미인지 판단하기 어려우면
     recommend로 추측하지 말고 qa로 분류하세요.

2. qa → 메뉴 정보 질문
   - 예: "아메리카노 얼마야?", "카페라떼 칼로리 뭐야?"

3. order → 주문 또는 행동 요청 (결제수단 언급 없음)
   - 예: "아메리카노 하나 줘", "라떼 주문할게", "이거 담아줘"
   - 예: "T멤버십 할인되는 거 담아줘", "KT 할인 메뉴 줘" (할인 대상 메뉴를 주문하는 경우)

4. coupon → 바코드 쿠폰 또는 모바일 상품권(금액권/음료권) 사용 요청
   - 예: "쿠폰 있어요", "쿠폰 사용하고 싶어", "상품권 쓸게요", "바코드 쿠폰 있는데"
   - 주의: T멤버십, KT VIP, CJ ONE, T우주, 카드, 카카오페이 등은 coupon이 아니라 payment

5. payment → 결제 수단을 선택하거나 결제를 진행하려는 요청 (메뉴 언급 없음)
   - 예: "결제할게", "카드로 결제할게", "카카오페이 쓸게", "계산해줘"
   - 예: "KT VIP로 결제할게", "T멤버십 쓸게", "CJ ONE으로 할게", "T우주 우주패스로 결제"
   - 주의: "KT 할인 뭐야?", "T멤버십 혜택이 뭐야?", "할인 정보 알려줘" 처럼 정보를 묻는 질문은 qa

6. order_and_pay → 메뉴 주문과 결제수단을 동시에 언급하는 요청
   - 예: "아메리카노 한 잔 신용카드로 결제할게", "라떼 하나 카카오페이로 결제할게"
   - 예: "카페라떼 두 잔 카드 결제", "아이스 아메리카노 네이버페이로 계산해줘"
   - 메뉴명 + 결제수단이 동시에 포함된 경우 반드시 order_and_pay


규칙:
- 반드시 아래 여섯 중 하나만 출력하세요
- 다른 말 절대 하지 마세요

출력:
recommend / qa / order / coupon / payment / order_and_pay

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
