import re
DISCOUNT_MENU_MAP = {
    "T멤버십": "아메리카노",
    "tmembership": "아메리카노",
}

NOISE_TOKENS = {"T", "KT", "CJ", "SKT"}

# 옵션 종류별로 선택할 수 있는 메뉴 카테고리. 여기에 없는 조합은 "옵션 설정 불가" 예외로 처리한다.
# (사이즈는 메뉴 DB의 sizes 값으로 따로 검증한다.)
OPTION_ALLOWED_CATEGORIES = {
    "shot": {"커피", "디카페인"},
    "light": {"커피", "디카페인"},
    "syrup": {"커피", "디카페인", "티"},
    "cream": {"커피", "디카페인", "스무디"},
}
OPTION_LABELS = {
    "shot": "샷 추가",
    "light": "연하게",
    "syrup": "시럽",
    "cream": "크림",
    "size": "사이즈",
}


def _josa(word: str, with_final: str, without_final: str) -> str:
    """받침 유무에 맞는 조사를 붙인다. 한글로 끝나지 않으면(예: ")") 'A(B)' 형태로 표기한다."""
    # "아이스 카페라떼 (시럽 적게)"처럼 괄호로 끝나면 괄호 앞 단어 기준으로 받침을 본다
    stripped = re.sub(r"\s*\([^)]*\)\s*$", "", word).rstrip(") ")
    code = ord(stripped[-1]) if stripped else 0
    if 0xAC00 <= code <= 0xD7A3:
        return word + (with_final if (code - 0xAC00) % 28 else without_final)
    return f"{word}{with_final}({without_final})"


def _is_noise_menu(menu: str | None) -> bool:
    if not menu:
        return True
    cleaned = menu.strip()
    return len(cleaned) <= 2 or cleaned.upper() in NOISE_TOKENS


def apply_discount_menu_fallback(entities: list[dict], query: str, menu_names: list[str]) -> list[dict]:
    """할인 수단만 언급하고 메뉴를 추출하지 못한 경우, 그 할인의 대상 메뉴로 보완한다."""
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


def _merge_option_details(entity: dict) -> list[dict]:
    """구조화된 옵션(option_details)에 기존 키워드 옵션(options)을 합친다. 이름 기준 중복 제거."""
    details = [dict(d) for d in entity.get("option_details", [])]
    seen = {d["name"] for d in details}
    for name in entity.get("options", []):
        if name not in seen:
            details.append({"kind": "other", "name": name, "count": 1})
            seen.add(name)
    return details


def entities_to_orders(entities: list[dict]) -> list[dict]:
    orders = []
    for entity in entities:
        base_menu = None
        temperature = "ICE"
        raw = entity["menu"]
        if raw:
            if raw.startswith("아이스 "):
                base_menu = raw[len("아이스 "):]
                temperature = "ICE"
            elif raw.startswith("핫 "):
                base_menu = raw[len("핫 "):]
                temperature = "HOT"
            else:
                base_menu = raw
                temperature = "HOT" if "hot" in entity["attributes"] else "ICE"
        details = _merge_option_details(entity)
        orders.append({
            "menu": base_menu,
            "temperature": temperature,
            "quantity": entity["quantity"],
            "options": [d["name"] for d in details],
            "option_details": details,
            "packaging": entity.get("packaging"),
            "needs_recommendation": entity["needs_recommendation"],
        })
    return orders


def split_sold_out(orders: list[dict], sold_out_names: set[str]) -> tuple[list[dict], list[str]]:
    """품절 메뉴는 담을 목록에서 빼고, 품절 메뉴명 목록을 따로 돌려준다."""
    available = [o for o in orders if o["menu"] not in sold_out_names]
    sold_out: list[str] = []
    for o in orders:
        if o["menu"] in sold_out_names and o["menu"] not in sold_out:
            sold_out.append(o["menu"])
    return available, sold_out


def allowed_option_labels(menu_info: dict) -> list[str]:
    """해당 메뉴에서 선택할 수 있는 옵션 이름 목록 (안내 문구용)."""
    labels = [OPTION_LABELS[k] for k, cats in OPTION_ALLOWED_CATEGORIES.items()
              if k != "light" and menu_info.get("category") in cats]
    if menu_info.get("sizes"):
        labels.append("사이즈")
    return labels


def validate_options(orders: list[dict], menus: list[dict]) -> tuple[list[dict], list[str]]:
    """메뉴별로 선택 불가능한 옵션을 걸러내고, 안내 문구를 돌려준다.
    (예: 에이드·주스에 '샷 추가'는 불가, 주스에 '크림'은 불가, 메뉴가 지원하지 않는 사이즈)
    불가한 옵션만 빼고 메뉴는 그대로 담는다."""
    by_name = {m["name"]: m for m in menus}
    notices: list[str] = []
    for order in orders:
        info = by_name.get(order["menu"]) if order["menu"] else None
        if info is None:
            continue
        # 메뉴가 지원하지 않는 온도면 지원하는 온도로 맞춘다 (예: 에스프레소는 HOT만, 스무디는 ICE만)
        temps = info.get("temps") or []
        if temps and order["temperature"] not in temps and len(temps) == 1:
            order["temperature"] = temps[0]
            only = "따뜻한" if temps[0] == "HOT" else "아이스"
            how = "따뜻하게" if temps[0] == "HOT" else "아이스로"
            notices.append(f"{_josa(order['menu'], '은', '는')} {only} 음료로만 주문할 수 있어서 {how} 담았어요.")
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
    # 같은 안내가 중복되지 않게
    return orders, list(dict.fromkeys(notices))


def _option_text(order: dict) -> str:
    parts = []
    for d in order.get("option_details", []):
        parts.append(f"{d['name']} ×{d['count']}" if d.get("count", 1) > 1 else d["name"])
    if order.get("packaging"):
        parts.append("포장")
    return f" ({', '.join(parts)})" if parts else ""


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
            f"{'아이스' if o['temperature'] == 'ICE' else '따뜻한'} {o['menu']}{_option_text(o)}"
            for o in named
        )
        if pay_suffix is None:
            parts.append(f"{_josa(items_str, '을', '를')} 장바구니에 담았습니다.")
        else:
            parts.append(f"{_josa(items_str, '을', '를')} 장바구니에 담고{pay_suffix}")
    for name in sold_out:
        text = f"{_josa(name, '은', '는')} 현재 품절이에요."
        alts = (alternatives or {}).get(name)
        if alts:
            text += f" 대신 {_josa(', '.join(alts), '은', '는')} 어떠세요? 번호로 말씀해 주셔도 돼요."
        parts.append(text)
    parts.extend(notices or [])
    return " ".join(parts) if parts else "어떤 메뉴를 주문하시겠어요?"
