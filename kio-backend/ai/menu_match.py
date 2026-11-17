"""메뉴판에 없는 이름을 비슷한 메뉴로 잇고, 재료·과일로 메뉴를 찾는다."""
import re

from ai.entity import normalize_text
from ai.order import _josa

# 메뉴판에 없는 이름 -> 비슷한 우리 메뉴 (패턴, 우리 메뉴 이름에 들어 있는 말, 맛 설명)
MENU_ALIASES = [
    (re.compile(r"코코아|코코어|핫초코|핫초콜릿|초콜릿\s*음료|(?:벨기[에안]|벨지안|발로나)\s*(?:산\s*)?초코(?:\s*라떼)?"), "초코라떼", "달콤하고 진한 초콜릿 맛이에요."),
    (re.compile(r"(?<!흑당)(?<!흑당 )(?:버블\s*티|타피오카|보바|펄\s*밀크티|펄\s*음료|흑당\s*라떼|흑당\s*밀크)"), "흑당버블", "쫀득한 펄이 들어간 달콤한 흑당 음료예요."),
    (re.compile(r"카페\s*모카|(?<![가-힣])모카|초코\s*우유|초코\s*쉐이크|초콜릿\s*라떼"), "초코라떼", "달콤하고 진한 초콜릿 맛이에요."),
    (re.compile(r"플랫\s*화이트|라떼\s*마끼?아또|우유\s*커피|밀크\s*커피|카페\s*오레|코르타도"), "카페라떼", "우유가 부드럽게 들어간 커피예요."),
    (re.compile(r"돌체|연유\s*라떼|아인\s*슈페너|슈페너|헤이즐넛\s*라떼|바닐라\s*빈"), "바닐라라떼", "달콤하고 부드러운 라떼예요."),
    (re.compile(r"콜드\s*브루|더치|리스트레토|룽고|도피오|블랙\s*커피|드립\s*커피|아이스\s*커피"), "아메리카노", "깔끔하고 진한 커피예요."),
    (re.compile(r"프라페|쉐이크|셰이크|슬러시|요거트\s*음료|생과일\s*(?:갈이|스무디)"), "딸기스무디", "시원하게 갈아 만든 음료예요."),
    (re.compile(r"딸기\s*우유|딸기\s*밀크|딸기\s*쉐이크"), "딸기라떼", "딸기 맛이 진한 우유 음료예요."),
    (re.compile(r"사이다|콜라|탄산\s*(?:음료|수)?|소다|스파클링|스프라이트"), "청포도에이드", "상큼하고 톡 쏘는 탄산 음료예요."),
    (re.compile(r"오렌지\s*에이드|유자\s*에이드|라임\s*에이드|파인애플\s*에이드|복숭아\s*에이드"), "자몽에이드", "새콤달콤한 에이드예요."),
    (re.compile(r"토마토\s*주스|생과일\s*주스|사과\s*주스|포도\s*주스|딸기\s*주스|바나나\s*주스|바나나\s*우유"), "딸기바나나", "과일을 갈아 만든 주스예요."),
    (re.compile(r"보리차|허브\s*티|생강차|둥굴레|카모마일|카밀레"), "캐모마일", "카페인이 없고 은은한 따뜻한 차예요."),
    (re.compile(r"녹차|말차|그린\s*티"), "녹차라떼", "진한 녹차 맛 라떼예요."),
    (re.compile(r"홍차|잉글리쉬|아이스\s*티|복숭아\s*티"), "얼그레이", "향긋한 홍차예요."),
    (re.compile(r"민트\s*티|박하|애플\s*민트|스피아민트"), "페퍼민트", "시원하고 개운한 민트차예요."),
    (re.compile(r"유자차|레몬\s*티|자몽\s*티|과일\s*차|베리\s*티"), "히비스커스", "새콤한 과일 향 차예요."),
]


def resolve_owned_aliases(query: str, menus: list[dict], confirmed: list[str]) -> str:
    """"버블티로 두 잔 달라니까"처럼 말한 이름이 우리 메뉴 이름의 일부이고(버블티 ⊂ 흑당버블티) 그 메뉴를 방금 권해서
    손님이 이미 알고 있으면(confirmed), 그 메뉴 이름으로 바꿔 곧바로 주문으로 잇는다. 처음 말했으면 먼저 확인한다."""
    for rx, key, _ in MENU_ALIASES:
        hit = rx.search(query)
        if not hit:
            continue
        said = normalize_text(hit.group(0))
        owners = [m["name"] for m in menus if not m["sold_out"] and normalize_text(key) in normalize_text(m["name"])
                  and said in normalize_text(m["name"])]
        if owners and owners[0] in confirmed:
            return query[:hit.start()] + owners[0] + query[hit.end():]
    return query


def alias_answer(query: str, menus: list[dict]) -> tuple[str, list[str]] | None:
    """코코아·벨기에 초코라떼·버블티처럼 메뉴판에 없는 이름을 말하면 비슷한 우리 메뉴를 권한다."""
    qn = normalize_text(query)
    for rx, key, taste in MENU_ALIASES:
        hit = rx.search(query) or rx.search(qn)
        if not hit:
            continue
        said = normalize_text(hit.group(0))
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


FRUITS = ("망고", "딸기", "바나나", "블루베리", "청포도", "포도", "레몬", "자몽", "오렌지", "복숭아",
          "사과", "키위", "수박", "유자", "멜론", "체리", "라임", "파인애플", "베리")
INGREDIENTS = FRUITS + ("초코", "바닐라", "카라멜", "요거트", "민트", "허니", "고구마")
_RE_FRUIT_ASK = re.compile(r"과일")
_RE_STOCK_ASK = re.compile(r"있|없|팔|들어|뭐|메뉴|골라|맛|종류|보여")
_RE_SHOW = re.compile(r"보여\s*(?:줘|주세요|줄래|주라|줘요)")  # "보여줘"는 주문이 아니라 보여 달라는 말
_RE_ORDER_WORD = re.compile(r"주세요|주셔|줘|줄래|담아|담을게|할게|하겠|시킬게|주문")
MAX_SHOWN = 10


def _price(m: dict) -> str:
    p = m.get("price")
    return f" ({p:,}원)" if isinstance(p, int) and p > 0 else ""


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
