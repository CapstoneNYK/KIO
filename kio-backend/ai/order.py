DISCOUNT_MENU_MAP = {
    "T멤버십": "아메리카노",
    "tmembership": "아메리카노",
}

NOISE_TOKENS = {"T", "KT", "CJ", "SKT"}


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
                "attributes": [],
                "needs_recommendation": False,
            }]
    return entities


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
        orders.append({
            "menu": base_menu,
            "temperature": temperature,
            "quantity": entity["quantity"],
            "options": entity.get("options", []),
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


def cart_answer(named: list[dict], sold_out: list[str], pay_suffix: str | None = None) -> str:
    parts = []
    if named:
        items_str = ", ".join(
            f"{'아이스' if o['temperature'] == 'ICE' else '따뜻한'} {o['menu']}" for o in named
        )
        if pay_suffix is None:
            parts.append(f"{items_str}을(를) 장바구니에 담았습니다.")
        else:
            parts.append(f"{items_str}을(를) 장바구니에 담고{pay_suffix}")
    if sold_out:
        parts.append(f"{', '.join(sold_out)}은(는) 현재 품절이에요.")
    return " ".join(parts) if parts else "어떤 메뉴를 주문하시겠어요?"
