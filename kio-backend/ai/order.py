# [order.py] 해석된 말(entity) → 실제 주문(order) 변환과 검증: 온도/옵션 정리, 품절·재고 처리, 장바구니 안내 문구 생성.
# 공용 도우미 _josa()(을/를·은/는 붙이기)도 여기 있어서 dialog.py, menu_match.py 가 가져다 쓴다.
import re
# 할인 이름 → 대상 메뉴. 메뉴 말 없이 'T멤버십 할인되는 거'라고만 하면 이 메뉴로 채운다. (대소문자 두 가지 표기를 따로 둠)
DISCOUNT_MENU_MAP = {
    "T멤버십": "아메리카노",
    "tmembership": "아메리카노",
}

# 메뉴처럼 잘못 인식된 잡음 단어(T, KT, CJ …) — 메뉴가 아닌 것으로 취급
NOISE_TOKENS = {"T", "KT", "CJ", "SKT"}

# 옵션 종류별로 허용되는 메뉴 카테고리(예: 샷 추가는 커피/디카페인/티만).
# [겹침] 아래 DIALOG_ASK_CATEGORIES 의 shot/light 는 이 표와 똑같은 값이다(되묻기용은 화면에서 고를 수 있는 것만 남긴 부분집합).
OPTION_ALLOWED_CATEGORIES = {
    "shot": {"커피", "디카페인", "티"},
    "light": {"커피", "디카페인"},
    "syrup": {"커피", "디카페인"},
    "cream": {"커피", "디카페인", "스무디"},
}
# 대화형으로 되묻는 옵션: 주문 화면(MenuModal)에서 실제로 고를 수 있는 것만
# 대화형으로 '되묻는' 옵션 → 허용 카테고리. 주문 화면(MenuModal)에서 실제로 고를 수 있는 것만
DIALOG_ASK_CATEGORIES = {
    "shot": {"커피", "디카페인", "티"},
    "light": {"커피", "디카페인"},
}
# 옵션 종류 → 사용자에게 보여 줄 이름
OPTION_LABELS = {
    "shot": "샷 추가",
    "light": "연하게",
    "syrup": "시럽",
    "cream": "크림",
    "size": "사이즈",
}


# 단어 끝 글자 받침 유무에 따라 조사를 붙인다(은/는, 이/가, 을/를 …). 한글이 아니면 '은(는)'처럼 둘 다 표기.
# [겹침] cart_command._eul/_eun 이 같은 기능을 따로 구현하고 있다.
def _josa(word: str, with_final: str, without_final: str) -> str:
    stripped = re.sub(r"\s*\([^)]*\)\s*$", "", word).rstrip(") ")
    code = ord(stripped[-1]) if stripped else 0
    if 0xAC00 <= code <= 0xD7A3:
        return word + (with_final if (code - 0xAC00) % 28 else without_final)
    return f"{word}{with_final}({without_final})"


# 메뉴가 비었거나 2글자 이하이거나 잡음 단어(T/KT/CJ…)면 '메뉴가 아님'으로 판정
def _is_noise_menu(menu: str | None) -> bool:
    if not menu:
        return True
    cleaned = menu.strip()
    return len(cleaned) <= 2 or cleaned.upper() in NOISE_TOKENS


# 모든 항목이 잡음 메뉴일 때, 말 속에 할인 이름(T멤버십 등)이 있으면 그 할인 대상 메뉴(아이스 1잔)로 대체
def apply_discount_menu_fallback(entities: list[dict], query: str, menu_names: list[str]) -> list[dict]:
    if not all(_is_noise_menu(e.get("menu")) for e in entities):
        return entities
    q_norm = query.replace(" ", "")
    for keyword, menu in DISCOUNT_MENU_MAP.items():
        if keyword.replace(" ", "") in q_norm and menu in menu_names:
            return [{
                "menu": menu,
                "quantity": 1,
                "temperature": "ICE",
                "options": [],
                "option_details": [],
                "packaging": None,
                "attributes": [],
                "needs_recommendation": False,
            }]
    return entities


# options(이름만) 중 option_details 에 없는 것을 kind='other' 로 합쳐 하나의 목록으로
def _merge_option_details(entity: dict) -> list[dict]:
    details = [dict(d) for d in entity.get("option_details", [])]
    seen = {d["name"] for d in details}
    for name in entity.get("options", []):
        if name not in seen:
            details.append({"kind": "other", "name": name, "count": 1})
            seen.add(name)
    return details


# entity 목록 → 주문 목록. 메뉴 이름 앞의 '아이스 '/'핫 '을 떼서 온도로 옮기고,
# 온도를 명시했는지(temp_explicit)를 기록한다(명시 안 했으면 기본 ICE).
def entities_to_orders(entities: list[dict]) -> list[dict]:
    orders = []
    for entity in entities:
        base_menu = None
        temperature = "ICE"
        explicit = "hot" in entity["attributes"] or "ice" in entity["attributes"]
        raw = entity["menu"]
        if raw:
            if raw.startswith("아이스 "):
                base_menu = raw[len("아이스 "):]
                temperature = "ICE"
                explicit = True
            elif raw.startswith("핫 "):
                base_menu = raw[len("핫 "):]
                temperature = "HOT"
                explicit = True
            else:
                base_menu = raw
                temperature = "HOT" if "hot" in entity["attributes"] else "ICE"
        details = _merge_option_details(entity)
        orders.append({
            "menu": base_menu,
            "temperature": temperature,
            "temp_explicit": explicit,
            "quantity": entity["quantity"],
            "options": [d["name"] for d in details],
            "option_details": details,
            "packaging": entity.get("packaging"),
            "needs_recommendation": entity["needs_recommendation"],
        })
    return orders


# 주문을 '주문 가능'과 '품절 메뉴 이름 목록'으로 나눔
def split_sold_out(orders: list[dict], sold_out_names: set[str]) -> tuple[list[dict], list[str]]:
    available = [o for o in orders if o["menu"] not in sold_out_names]
    sold_out: list[str] = []
    for o in orders:
        if o["menu"] in sold_out_names and o["menu"] not in sold_out:
            sold_out.append(o["menu"])
    return available, sold_out


# 재고 제한 적용: (재고 − 이미 담은 수 − 이번에 담는 수)만큼만 허용. 남는 게 없으면 제외, 부족하면 수량을 줄이고 안내 문구 생성
def limit_by_stock(orders: list[dict], menus: list[dict], in_cart: dict[str, int]) -> tuple[list[dict], list[str]]:
    by_name = {m["name"]: m for m in menus}
    taken: dict[str, int] = {}
    kept: list[dict] = []
    notices: list[str] = []
    for order in orders:
        info = by_name.get(order["menu"]) if order["menu"] else None
        stock = info.get("stock") if info else None
        if stock is None:
            kept.append(order)
            continue
        name = order["menu"]
        remaining = max(0, stock - in_cart.get(name, 0) - taken.get(name, 0))
        want = order.get("quantity", 1)
        have = in_cart.get(name, 0)
        why = f"재고가 {stock}개뿐이고 이미 {have}개 담겨 있어서" if have else f"재고가 {stock}개뿐이라"
        if remaining <= 0:
            notices.append(f"{_josa(name, '은', '는')} {why} 더 담을 수 없어요.")
            continue
        if want > remaining:
            order["quantity"] = remaining
            notices.append(f"{_josa(name, '은', '는')} {why} {remaining}개만 담았어요.")
        taken[name] = taken.get(name, 0) + order["quantity"]
        kept.append(order)
    return kept, list(dict.fromkeys(notices))


# 이 메뉴에서 선택 가능한 옵션 이름 목록(안내 문구용). '연하게'는 안내에서 제외
def allowed_option_labels(menu_info: dict) -> list[str]:
    labels = [OPTION_LABELS[k] for k, cats in OPTION_ALLOWED_CATEGORIES.items()
              if k != "light" and menu_info.get("category") in cats]
    if menu_info.get("sizes"):
        labels.append("사이즈")
    return labels


# 메뉴가 지원하지 않는 옵션을 걸러내고 안내 문구 생성.
#  - 온도가 한 가지뿐인 메뉴는 그 온도로 고정
#  - 온도를 말 안 해서 기본(아이스)으로 담은 메뉴는 따로 모아 한 번에 안내
#  - 카테고리/사이즈 허용 목록에 없는 옵션은 제거
def validate_options(orders: list[dict], menus: list[dict]) -> tuple[list[dict], list[str]]:
    by_name = {m["name"]: m for m in menus}
    notices: list[str] = []
    defaulted: list[str] = []
    for order in orders:
        info = by_name.get(order["menu"]) if order["menu"] else None
        if info is None:
            continue
        temps = info.get("temps") or []
        if temps and order["temperature"] not in temps and len(temps) == 1:
            order["temperature"] = temps[0]
            only = "따뜻한" if temps[0] == "HOT" else "아이스"
            how = "따뜻하게" if temps[0] == "HOT" else "아이스로"
            notices.append(f"{_josa(order['menu'], '은', '는')} {only} 음료로만 주문할 수 있어서 {how} 담았어요.")
        elif (not order.get("temp_explicit", True) and order["temperature"] == "ICE"
                and "HOT" in temps and order["menu"] not in defaulted):
            defaulted.append(order["menu"])
        kept = []
        for d in order.get("option_details", []):
            kind = d.get("kind")
            ok = True
            if kind in OPTION_ALLOWED_CATEGORIES:
                ok = info["category"] in OPTION_ALLOWED_CATEGORIES[kind]
            elif kind == "size":
                size = d["name"].split()[-1]
                ok = size in info.get("sizes", [])
            if ok:
                kept.append(d)
                continue
            allowed = allowed_option_labels(info)
            label = OPTION_LABELS.get(kind, d["name"])
            hint = f" 선택할 수 있는 옵션: {', '.join(allowed)}." if allowed else " 이 메뉴는 선택할 수 있는 옵션이 없어요."
            notices.append(f"{order['menu']}에는 {label} 옵션을 선택할 수 없어서 빼고 담았어요.{hint}")
        order["option_details"] = kept
        order["options"] = [d["name"] for d in kept]
    if defaulted:
        names = ", ".join(defaulted)
        notices.append(f"온도를 말씀하지 않으셔서 {_josa(names, '은', '는')} 아이스로 담았어요. 따뜻하게 드시려면 '다 핫으로 바꿔줘'라고 말씀해 주세요.")
    return orders, list(dict.fromkeys(notices))


# 주문의 옵션을 ' (샷추가 ×2, 포장)' 형태 문자열로
def _option_text(order: dict) -> str:
    parts = []
    for d in order.get("option_details", []):
        parts.append(f"{d['name']} ×{d['count']}" if d.get("count", 1) > 1 else d["name"])
    if order.get("packaging"):
        parts.append("포장")
    return f" ({', '.join(parts)})" if parts else ""


# 장바구니 담기 결과 안내 문장 생성: 담은 메뉴 → 품절 안내(+대체 메뉴) → 기타 공지 순으로 이어 붙임.
# pay_suffix 가 있으면 '담고 …'로 결제 안내를 이어서 말한다.
def cart_answer(
    named: list[dict],
    sold_out: list[str],
    pay_suffix: str | None = None,
    alternatives: dict[str, list[str]] | None = None,
    notices: list[str] | None = None,
) -> str:
    parts = []
    if named:
        items_str = ", ".join(
            f"{'아이스' if o['temperature'] == 'ICE' else '따뜻한'} {o['menu']}"
            f"{' ' + str(o['quantity']) + '잔' if o.get('quantity', 1) > 1 else ''}{_option_text(o)}"
            for o in named
        )
        bold = f"**{items_str}**" + _josa(items_str, "을", "를")[len(items_str):]  # 담은 메뉴는 굵게(프론트가 **…** 를 굵게 그린다)
        if pay_suffix is None:
            parts.append(f"{bold} 장바구니에 담았습니다.")
        else:
            parts.append(f"{bold} 장바구니에 담고{pay_suffix}")
    for name in sold_out:
        text = f"{_josa(name, '은', '는')} 현재 품절이에요."
        alts = (alternatives or {}).get(name)
        if alts:
            text += f" 대신 {_josa(', '.join(alts), '은', '는')} 어떠세요? 번호로 말씀해 주셔도 돼요."
        parts.append(text)
    parts.extend(notices or [])
    return " ".join(parts) if parts else "어떤 메뉴를 주문하시겠어요?"
