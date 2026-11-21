# [menu_match.py] 메뉴판에 없는 이름(코코아·버블티 등)을 비슷한 우리 메뉴로 연결하고, 재료·과일로 메뉴를 찾아 보여 준다.
"""메뉴판에 없는 이름을 비슷한 메뉴로 잇고, 재료·과일로 메뉴를 찾는다."""
import re

from ai.korean import normalize_text, rx_keep
from ai.order import _josa

# 메뉴판에 없는 이름 -> 비슷한 우리 메뉴 (패턴, 우리 메뉴 이름에 들어 있는 말, 맛 설명)
# 메뉴판에 없는 이름 → 비슷한 우리 메뉴. 각 항목: (패턴, 우리 메뉴 이름에 들어 있는 말, 맛 설명).
# ※ 위에서부터 처음 맞는 규칙이 선택된다 → 한 문장이 여러 규칙에 걸리면 위쪽이 이긴다.
MENU_ALIASES = [
    (re.compile(r"코코아|코코어|핫초코|핫초콜릿|초콜릿\s*음료|(?:벨기[에안]|벨지안|발로나)\s*(?:산\s*)?초코(?:\s*라떼)?"), "초코라떼", "달콤하고 진한 초콜릿 맛이에요."),
    (re.compile(r"(?<!흑당)(?<!흑당 )(?:버블\s*티|타피오카|보바|펄\s*밀크티|펄\s*음료|흑당\s*라떼|흑당\s*밀크)"), "흑당버블", "쫀득한 펄이 들어간 달콤한 흑당 음료예요."),
    (re.compile(r"카페\s*모카|(?<![가-힣])모카|초코\s*우유|초코\s*쉐이크|초콜릿\s*라떼"), "초코라떼", "달콤하고 진한 초콜릿 맛이에요."),
    (re.compile(r"플랫\s*화이트|라떼\s*마끼?아또|우유\s*커피|밀크\s*커피|카페\s*오레|코르타도"), "카페라떼", "우유가 부드럽게 들어간 커피예요."),
    (re.compile(r"돌체|연유\s*라떼|아인\s*슈페너|슈페너|헤이즐넛\s*라떼|바닐라\s*빈"), "바닐라라떼", "달콤하고 부드러운 라떼예요."),
    (re.compile(r"콜드\s*브루|더치|리스트레토|룽고|도피오|블랙\s*커피|드립\s*커피|아이스\s*커피"), "아메리카노", "깔끔하고 진한 커피예요."),
    # [겹침] '쉐이크/셰이크'가 여기에 있어서, 아래 '딸기 쉐이크'(→딸기라떼) 규칙보다 먼저 걸린다(실행 확인: '딸기 쉐이크'는 딸기스무디로 연결됨)
    # [수정] 구체적인 '딸기 우유/밀크/쉐이크' 규칙을 일반 '쉐이크' 규칙보다 위로 옮김.
    #        (예전엔 아래 '프라페|쉐이크' 규칙이 먼저 맞아서 '딸기 쉐이크'가 이 규칙에 도달하지 못했다)
    (re.compile(r"딸기\s*우유|딸기\s*밀크|딸기\s*쉐이크"), "딸기라떼", "딸기 맛이 진한 우유 음료예요."),
    (re.compile(r"프라페|쉐이크|셰이크|슬러시|요거트\s*음료|생과일\s*(?:갈이|스무디)"), "딸기스무디", "시원하게 갈아 만든 음료예요."),
    (re.compile(r"사이다|콜라|탄산\s*(?:음료|수)?|소다|스파클링|스프라이트"), "청포도에이드", "상큼하고 톡 쏘는 탄산 음료예요."),
    (re.compile(r"오렌지\s*에이드|유자\s*에이드|라임\s*에이드|파인애플\s*에이드|복숭아\s*에이드"), "자몽에이드", "새콤달콤한 에이드예요."),
    (re.compile(r"토마토\s*주스|생과일\s*주스|사과\s*주스|포도\s*주스|딸기\s*주스|바나나\s*주스|바나나\s*우유"), "딸기바나나", "과일을 갈아 만든 주스예요."),
    (re.compile(r"보리차|허브\s*티|생강차|둥굴레|카모마일|카밀레"), "캐모마일", "카페인이 없고 은은한 따뜻한 차예요."),
    (re.compile(r"녹차|말차|그린\s*티"), "녹차라떼", "진한 녹차 맛 라떼예요."),
    (re.compile(r"홍차|잉글리쉬|아이스\s*티|복숭아\s*티"), "얼그레이", "향긋한 홍차예요."),
    (re.compile(r"민트\s*티|박하|애플\s*민트|스피아민트"), "페퍼민트", "시원하고 개운한 민트차예요."),
    (re.compile(r"유자차|레몬\s*티|자몽\s*티|과일\s*차|베리\s*티"), "히비스커스", "새콤한 과일 향 차예요."),
]


# 말한 이름이 우리 메뉴의 정식 이름 안에 이미 들어 있으면(녹차라떼 속 '녹차') 별칭 풀이를 하지 않기 위한 검사
def _inside_full_name(qn: str, said: str, menus: list[dict]) -> bool:
    """말한 이름이 우리 메뉴의 정식 이름 안에 이미 들어 있으면(녹차라떼 안의 '녹차') 별칭 풀이를 하지 않는다."""
    for m in menus:
        nm = normalize_text(m["name"])
        if said in nm and nm in qn:
            return True
    return False


# '버블티로 두 잔 달라니까'처럼 말한 이름이 우리 메뉴 이름의 일부(버블티 ⊂ 흑당버블티)이고, 그 메뉴를 방금 권해서
# 손님이 이미 아는 상태(confirmed)면 정식 메뉴 이름으로 바꿔 바로 주문으로 잇는다. 처음 말한 거면 먼저 확인(alias_answer)한다.
def resolve_owned_aliases(query: str, menus: list[dict], confirmed: list[str]) -> str:
    """"버블티로 두 잔 달라니까"처럼 말한 이름이 우리 메뉴 이름의 일부이고(버블티 ⊂ 흑당버블티) 그 메뉴를 방금 권해서
    손님이 이미 알고 있으면(confirmed), 그 메뉴 이름으로 바꿔 곧바로 주문으로 잇는다. 처음 말했으면 먼저 확인한다."""
    qn = normalize_text(query)
    for rx, key, _ in MENU_ALIASES:
        hit = rx.search(query)
        if not hit:
            continue
        said = normalize_text(hit.group(0))
        if _inside_full_name(qn, said, menus):
            continue
        owners = [m["name"] for m in menus if not m["sold_out"] and normalize_text(key) in normalize_text(m["name"])
                  and said in normalize_text(m["name"])]
        if owners and owners[0] in confirmed:
            return query[:hit.start()] + owners[0] + query[hit.end():]
    return query


# 코코아·버블티처럼 메뉴판에 없는 이름을 말하면 비슷한 메뉴를 권하는 안내문과 후보 이름 목록을 반환(해당 없으면 None)
def alias_answer(query: str, menus: list[dict]) -> tuple[str, list[str]] | None:
    """코코아·벨기에 초코라떼·버블티처럼 메뉴판에 없는 이름을 말하면 비슷한 우리 메뉴를 권한다."""
    qn = normalize_text(query)
    for rx, key, taste in MENU_ALIASES:
        hit = rx.search(query) or rx.search(qn)
        if not hit:
            continue
        said = normalize_text(hit.group(0))
        if _inside_full_name(qn, said, menus):
            continue  # "녹차라떼 하나 줘" — 정식 메뉴 이름을 말한 것이라 비슷한 메뉴를 권하지 않는다
        picks = [m["name"] for m in menus if normalize_text(key) in normalize_text(m["name"]) and not m["sold_out"]]
        if not picks:
            continue
        name = picks[0]
        # 말한 이름이 우리 메뉴판 이름의 일부이거나 같으면(예: '복숭아 아이스티' 안의 '아이스티') 진짜 메뉴 이야기다
        owners = [m["name"] for m in menus if said in normalize_text(m["name"])]
        if owners and name not in owners:
            continue
        said_text = hit.group(0).strip()
        if owners:  # '버블티' -> '흑당 버블티'처럼 말한 이름이 추천 메뉴 안에 들어 있다
            head = f"{_josa(said_text, '은', '는')} {_josa(name, '이', '가')} 있어요."
        else:
            head = f"{_josa(said_text, '은', '는')} 없지만 {_josa(name, '이', '가')} 비슷해요."
        return (f"{head} {taste}\n1번 {name}\n"
                f"{_josa(name, '으로', '로')} 드릴까요? 번호나 이름으로 말씀해 주세요."), [name]
    return None


# 과일 단어 / 재료 단어(과일 + 초코·바닐라 등). '딸기 들어간 거 뭐 있어?' 검색용
FRUITS = ("망고", "딸기", "바나나", "블루베리", "청포도", "포도", "레몬", "자몽", "오렌지", "복숭아",
          "사과", "키위", "수박", "유자", "멜론", "체리", "라임", "파인애플", "베리")
INGREDIENTS = FRUITS + ("초코", "바닐라", "카라멜", "요거트", "민트", "허니", "고구마")
# '과일' 이라는 말 자체를 물어보는 표현
_RE_FRUIT_ASK = re.compile(r"과일")
# '있어요/뭐 있어/종류' — 메뉴 존재·목록을 묻는 표현
_RE_STOCK_ASK = re.compile(r"있|없|팔|들어|뭐|메뉴|골라|맛|종류|보여")
# '보여줘'는 주문이 아니라 보여 달라는 말이라 주문 동사 검사에서 제외하기 위한 정규식
_RE_SHOW = rx_keep(r"보여\s*(?:줘|주세요|줄래|주라|줘요)")  # "보여줘"는 주문이 아니라 보여 달라는 말
# 주문 동사. [겹침] fast_intent._RE_ORDER_VERB, cart_command._RE_ORDER_TALK 와 비슷한 목록
_RE_ORDER_WORD = rx_keep(r"주세요|주셔|줘|줄래|담아|담을게|할게|하겠|시킬게|주문")
# 한 번에 보여 줄 최대 메뉴 수
MAX_SHOWN = 10


# 가격을 ' (4,500원)' 형태로 (가격 정보가 없으면 빈 문자열)
def _price(m: dict) -> str:
    p = m.get("price")
    return f" ({p:,}원)" if isinstance(p, int) and p > 0 else ""


# '딸기 들어간 거 뭐 있어?', '과일 들어간 음료' — 이름에 그 재료가 든 주문 가능 메뉴를 번호 목록으로 보여 준다.
# 메뉴 이름을 정확히 말했거나 주문 동사가 있으면 None(그 메뉴 이야기이므로).
def ingredient_answer(query: str, menus: list[dict]) -> tuple[str, list[str]] | None:
    """"딸기 들어간 거 뭐 있어?", "과일 들어간 음료 뭐 있어?" — 이름에 그 재료(과일)가 든 메뉴를 빠짐없이 보여 준다."""
    qn = normalize_text(query)
    if not _RE_STOCK_ASK.search(qn) or _RE_ORDER_WORD.search(_RE_SHOW.sub("", qn)):
        return None
    if any(normalize_text(m["name"]) in qn for m in menus):
        return None  # 메뉴 이름을 정확히 말했으면 그 메뉴 이야기
    available = [m for m in menus if not m["sold_out"]]
    found = [(qn.index(normalize_text(w)), w) for w in INGREDIENTS if normalize_text(w) in qn]
    if found:
        word = min(found)[1]
        words, label = (word,), word
    elif _RE_FRUIT_ASK.search(qn):
        words, label = FRUITS, "과일"
    else:
        return None
    picks = [m for m in available if any(normalize_text(w) in normalize_text(m["name"]) for w in words)]
    if not picks:
        return None
    names = [m["name"] for m in picks][:MAX_SHOWN]
    if len(picks) == 1:
        n = names[0]
        return f"{label} 메뉴는 {_josa(n, '이', '가')} 있어요. {_josa(n, '으로', '로')} 드릴까요?", names
    lines = "\n".join(f"{i}번 {m['name']}{_price(m)}" for i, m in enumerate(picks[:MAX_SHOWN], 1))
    return (f"{_josa(label, '이', '가')} 들어간 메뉴는 {len(picks)}가지예요. 어느 걸로 드릴까요?\n{lines}\n"
            f"번호나 이름으로 말씀해 주세요."), names


# ── 메뉴판에 없는 '재료 + 종류' 이름(예: 블루베리 주스) 안내 ──
# 주문·질문에 '블루베리 주스'처럼 재료와 음료 종류를 붙여 말했는데 그 조합이 메뉴에 없으면,
# 다른 메뉴로 잘못 담지 않고 "메뉴에 없어요 + 비슷한 메뉴"를 보여 준다.
_TYPE_WORDS = {"주스": "주스", "쥬스": "주스", "스무디": "스무디", "에이드": "에이드", "라떼": "라떼"}
# 재료·맛 단어(메뉴 이름에서 뽑은 단어와 합쳐 쓴다)
_FLAVOR_WORDS = ("딸기", "바나나", "블루베리", "망고", "복숭아", "사과", "키위", "수박", "멜론", "포도", "청포도", "오렌지",
                 "레몬", "자몽", "라임", "파인애플", "토마토", "체리", "코코넛", "유자", "초코", "녹차", "말차", "바닐라",
                 "카라멜", "헤이즐넛", "민트", "오레오", "고구마", "흑당", "요거트", "생과일")


# 메뉴 이름들에서 재료 단어 모으기: 띄어쓰기 단어 + '딸기라떼'처럼 끝이 종류 단어면 앞부분
def _flavor_vocab(menus: list[dict]) -> list[str]:
    vocab = {normalize_text(w) for w in _FLAVOR_WORDS}
    for m in menus:
        for tok in m["name"].split():
            n = normalize_text(tok)
            for tw in _TYPE_WORDS:
                if n.endswith(tw) and len(n) > len(tw):
                    n = n[: -len(tw)]
                    break
            if len(n) >= 2 and n not in _TYPE_WORDS:
                vocab.add(n)
    return sorted(vocab, key=len, reverse=True)


def missing_menu_answer(query: str, menus: list[dict]) -> tuple[str, list[str]] | None:
    """"블루베리 주스 줘" — 재료+종류 조합이 메뉴판에 없으면 (안내 문구, 비슷한 메뉴 이름들). 있거나 해당 없으면 None."""
    qn = normalize_text(query)
    vocab = _flavor_vocab(menus)
    names_n = [(m, normalize_text(m["name"])) for m in menus]
    for tw, ttype in _TYPE_WORDS.items():
        pos = qn.find(normalize_text(tw))
        if pos <= 0:
            continue
        # 종류 단어 바로 앞에서부터 재료 단어를 거꾸로 모은다("딸기 바나나 블루베리 주스" → 블루베리, 바나나, 딸기)
        flavors, head = [], qn[:pos]
        while head:
            hit = next((f for f in vocab if head.endswith(f)), None)
            if not hit:
                break
            flavors.insert(0, hit)
            head = head[: -len(hit)]
        if not flavors:
            continue
        if any(normalize_text(ttype) in nn and all(f in nn for f in flavors) for _, nn in names_n):
            continue  # 그런 메뉴가 있다
        ranked = sorted(
            (m for m, nn in names_n if not m.get("sold_out") and (any(f in nn for f in flavors) or normalize_text(ttype) in nn)),
            key=lambda m: (-sum(f in normalize_text(m["name"]) for f in flavors),
                           0 if normalize_text(ttype) in normalize_text(m["name"]) else 1, m.get("id", 0)))
        if not any(any(f in normalize_text(m["name"]) for f in flavors) for m in ranked):
            ranked = [m for m in ranked if normalize_text(ttype) in normalize_text(m["name"])]
        shown = [m["name"] for m in ranked[:4]]
        phrase = f"{' '.join(flavors)} {ttype}"
        if not shown:
            return f"**{phrase}**{_josa(phrase, '은', '는')[len(phrase):]} 메뉴에 없어요. 다른 메뉴를 말씀해 주세요.", []
        lines = "\n".join(f"{i}번 {n}" for i, n in enumerate(shown, 1))
        return (f"**{phrase}**{_josa(phrase, '은', '는')[len(phrase):]} 메뉴에 없어요. 비슷한 메뉴는 이런 게 있어요.\n{lines}\n번호나 이름으로 말씀해 주세요.", shown)
    return None
