"""여러 파일이 따로 들고 있던 '온도(따뜻/차가움) 단어' 공통 목록.

파일마다 인정하는 단어가 조금씩 달라서(예: '얼음'·'아아'는 dialog/preference 에서만 온도 표현,
cart_command 에서는 '얼음'이 옵션 단어라 온도로 보지 않는다) 공통 줄기(CORE)만 여기 두고,
각 파일은 CORE + 자기만의 추가 단어(EXTRA)를 붙여서 쓴다. 정규식 조각(| 로 연결)이라 rx() 로 컴파일한다.
"""

# 따뜻함 공통 단어
HOT_CORE = "따뜻|따듯|따스|따숩|따땃|따끈|뜨끈|뜨듯|뜨신|뜨겁|뜨거|핫|hot"
# 차가움 공통 단어
ICE_CORE = "아이스|차갑|차가|시원|ice"

# '찬 거/찬 걸/차게…' 처럼 '차다' 활용형. dialog 와 cart_command 가 같이 쓴다(cart_command 는 2단계에서 추가).
ICE_COLD_FORMS = "차게|차거|찬거|찬걸|찬것|찬음료|찬커피"

# 파일별 추가 단어
HOT_EXTRA_DIALOG = "뜨아|따아|하스"
HOT_EXTRA_PREFERENCE = "뜨아|뜨라"
HOT_EXTRA_CART = "뜨아"
ICE_EXTRA_DIALOG = ICE_COLD_FORMS + "|찬물|얼음|아아"
ICE_EXTRA_PREFERENCE = "얼음|아아|아라|냉"
ICE_EXTRA_CART = ICE_COLD_FORMS  # 얼음·아아는 일부러 뺌('얼음 많이'는 옵션, '아아'는 메뉴 별명)

# "많이" 계열 정도 표현(시럽/샷 양을 많게). dialog 와 entity 가 같이 쓴다
LEVEL_MORE = "많이|듬뿍|넉넉|가득"
