"""의도 분류 파인튜닝용 초기(seed) 데이터셋 생성 스크립트.

실제 사용 로그(data/intent_logs.jsonl)가 쌓이기 전, 파인튜닝을 바로 시작해볼 수 있도록
기존 intent.py 프롬프트의 예시들을 바탕으로 다양한 변형 문장을 자동 생성한다.

실행 방법 (kio-backend 폴더에서):
    uv run python generate_intent_seed.py

메뉴 목록이 바뀌면 이 스크립트를 다시 실행해서 data/intent_seed.jsonl을 갱신하면 된다.
"""

import json
import random
from pathlib import Path

from ai.dictionary import MENU_KEYWORDS

random.seed(42)

MENUS = sorted(set(MENU_KEYWORDS.values()))

QTY_WORDS = ["한 잔", "두 잔", "세 잔", "하나", "둘", "셋", "네 잔"]
TEMP_PREFIX = ["", "아이스 ", "핫 ", "따뜻한 ", "차가운 "]

ORDER_TEMPLATES = [
    "{t}{menu} {qty} 주세요",
    "{t}{menu} {qty} 줘",
    "{t}{menu} {qty} 주문할게요",
    "{t}{menu} {qty} 담아줘",
    "{t}{menu} {qty} 주문이요",
    "{t}{menu} {qty} 부탁해요",
    "{menu} {qty}이랑 {menu2} {qty2} 주세요",
]

PAYMENT_PHRASES = [
    "신용카드로 결제할게요",
    "카드로 계산해주세요",
    "카카오페이로 결제할게요",
    "네이버페이로 계산해줘",
    "앱카드로 결제할게요",
    "KT VIP로 결제할게요",
    "T멤버십 할인 받고 결제할게요",
    "CJ ONE으로 결제해주세요",
    "T우주 우주패스로 결제할게요",
]

EXTRA_ORDERS = [
    "샷 추가해서 아메리카노 주세요",
    "연하게 카페라떼 한 잔이요",
    "T멤버십 할인되는 거 담아줘",
    "KT 할인 메뉴 줘",
    "얼음 많이 넣어서 아이스 아메리카노 주세요",
    "디카페인으로 바닐라라떼 한 잔 줘",
    "이거 장바구니에 담아줘",
    "아메리카노 세 잔 포장이요",
    "라떼 하나 텀블러에 담아주세요",
]

RECOMMEND_EXAMPLES = [
    "당 떨어지는데 음료 추천해줘",
    "달달한 거 뭐 있어?",
    "시원한 음료 추천해주세요",
    "따뜻한 거 뭐가 좋을까요?",
    "커피 말고 다른 거 추천해줘",
    "논커피 메뉴 추천해줘",
    "디카페인 중에 뭐가 맛있어?",
    "새콤한 거 마시고 싶은데 추천해줄래?",
    "스무디 중에 뭐가 인기 많아?",
    "오늘 날씨에 어울리는 음료 추천해줘",
    "저당 음료 뭐 있어?",
    "제로 시럽 음료 추천해줘",
    "잠 안 오는 음료로 추천해줘",
    "커피 처음인데 뭐가 좋을까?",
    "든든한 거 마시고 싶은데 뭐 있어?",
    "상큼한 에이드 추천해줘",
    "무난한 거로 추천해줘",
    "제일 잘 나가는 메뉴가 뭐예요?",
    "여름에 어울리는 음료 있어?",
    "부드러운 라떼 종류 추천해줘",
    "차 종류 중에 추천해줄 만한 거 있어?",
    "피곤할 때 마시면 좋은 거 있어?",
    "새로운 메뉴 추천해줘",
    "너무 달지 않은 걸로 추천해줘",
    "향긋한 차 추천해줘",
]

QA_EXAMPLES = [
    "아메리카노 얼마야?",
    "카페라떼 칼로리 뭐야?",
    "바닐라라떼 가격이 어떻게 되나요?",
    "메뉴에 어떤 게 있어요?",
    "디카페인 메뉴 있어요?",
    "이 음료 카페인 얼마나 들어있어요?",
    "T멤버십 혜택이 뭐야?",
    "KT 할인 뭐야?",
    "할인 정보 알려줘",
    "CJ ONE 할인은 어떻게 받아요?",
    "T우주 우주패스 혜택이 뭐예요?",
    "SKT 할인 뭐 있어요?",
    "지금 장바구니에 담은 거 할인 되나요?",
    "이 메뉴 알레르기 유발 성분 있어요?",
    "사이즈업 되나요?",
    "포장 가능한가요?",
    "매장에서 먹고 갈 수 있나요?",
    "영업시간이 어떻게 되나요?",
    "화장실 어디 있어요?",
    "와이파이 비밀번호 뭐예요?",
    "얼음 빼는 것도 가능해요?",
    "시럽 추가하면 얼마예요?",
]

COUPON_EXAMPLES = [
    "쿠폰 있어요",
    "쿠폰 사용하고 싶어",
    "상품권 쓸게요",
    "바코드 쿠폰 있는데",
    "모바일 상품권 쓸 수 있나요",
    "쿠폰 스캔해주세요",
    "음료 교환권 있어요",
    "기프티콘 사용할게요",
    "쿠폰 여기 있어요 찍어주세요",
    "적립 쿠폰 쓸게요",
]

PAYMENT_EXAMPLES = [
    "결제할게요",
    "카드로 결제할게요",
    "카카오페이 쓸게요",
    "계산해주세요",
    "네이버페이로 할게요",
    "앱카드로 계산할게요",
    "KT VIP로 결제할게요",
    "T멤버십 쓸게요",
    "CJ ONE으로 할게요",
    "T우주 우주패스로 결제할게요",
    "현금 말고 카드로 할게요",
    "결제 수단 바꿀게요",
    "그냥 카드로 해주세요",
]


def build_dataset() -> list[dict]:
    data: list[dict] = []

    def add(text: str, intent: str) -> None:
        data.append({"text": text, "intent": intent})

    for _ in range(60):
        tmpl = random.choice(ORDER_TEMPLATES)
        t = random.choice(TEMP_PREFIX)
        menu = random.choice(MENUS)
        qty = random.choice(QTY_WORDS)
        if "{menu2}" in tmpl:
            menu2 = random.choice([m for m in MENUS if m != menu])
            qty2 = random.choice(QTY_WORDS)
            text = tmpl.format(menu=menu, qty=qty, menu2=menu2, qty2=qty2)
        else:
            text = tmpl.format(t=t, menu=menu, qty=qty)
        add(text, "order")

    for t in EXTRA_ORDERS:
        add(t, "order")
    for t in RECOMMEND_EXAMPLES:
        add(t, "recommend")
    for t in QA_EXAMPLES:
        add(t, "qa")
    for t in COUPON_EXAMPLES:
        add(t, "coupon")
    for t in PAYMENT_EXAMPLES:
        add(t, "payment")

    for _ in range(45):
        menu = random.choice(MENUS)
        qty = random.choice(QTY_WORDS)
        t = random.choice(TEMP_PREFIX)
        pay_text = random.choice(PAYMENT_PHRASES)
        order_part = random.choice([
            f"{t}{menu} {qty}",
            f"{t}{menu} {qty} 주문하고",
            f"{t}{menu} {qty} 담고",
        ])
        add(f"{order_part} {pay_text}", "order_and_pay")

    random.shuffle(data)
    return data


def main() -> None:
    data = build_dataset()
    out_path = Path(__file__).parent / "data" / "intent_seed.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in data:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    from collections import Counter
    counts = Counter(d["intent"] for d in data)
    print(f"총 {len(data)}개 생성 -> {out_path}")
    for intent, count in counts.items():
        print(f"  {intent}: {count}")


if __name__ == "__main__":
    main()
