import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "kio_admin.db"

UPLOAD_DIR = Path(__file__).parent / "uploads" / "menu_images"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DISCOUNT_METHODS: dict[str, str] = {
    "kt": "KT VIP",
    "tmembership": "T멤버십",
    "uzu": "T우주",
    "cjone": "CJ ONE",
}

INITIAL_DISCOUNTS = [
    (
        "KT 멤버십 (VIP/VVIP 전용)",
        "kt",
        "바코드 스캔 시 구매 음료 1종 50% 할인\n"
        "이용 대상: KT 멤버십 VIP, VVIP 등급 고객에 한함\n"
        "단품 1잔에 한함, 당일 방문 시 적용\n"
        "매장 직원에게 KT 멤버십 바코드를 제시하여 스캔\n"
        "일부 특수 매장 및 배달 주문 제외, 타 할인/적립 중복 불가",
    ),
    (
        "T멤버십 T Day",
        "tmembership",
        "매월 지정된 T Day(월 1회)에 아이스 아메리카노 구매 시 30% 할인 (단품 1잔에 한함)\n"
        "T멤버십 매직 바코드 제시 시 할인 적용\n"
        "할인을 선택한 T멤버십 회원만 이용 가능\n"
        "월 1회 한정, 중복 할인 불가",
    ),
    (
        "T우주패스",
        "uzu",
        "우주패스 바코드 스캔 시 음료 1종 무료\n"
        "이용 방법: 매장 방문 → 바코드 제시 → 스캔 후 무료 음료 수령\n"
        "일부 품목 제외 및 매장별로 상이할 수 있음",
    ),
]

INITIAL_MENUS = [
    (1,  "아메리카노",          2000, "커피",    '["HOT","ICE"]', 0),
    (2,  "카페라떼",            3000, "커피",    '["HOT","ICE"]', 0),
    (3,  "카푸치노",            4500, "커피",    '["HOT","ICE"]', 0),
    (4,  "바닐라라떼",          5000, "커피",    '["HOT","ICE"]', 0),
    (5,  "카라멜마키아토",      5000, "커피",    '["HOT","ICE"]', 0),
    (6,  "에스프레소",          1500, "커피",    '["HOT"]',       0),
    (7,  "디카페인 아메리카노", 4500, "디카페인", '["HOT","ICE"]', 0),
    (8,  "디카페인 라떼",       5000, "디카페인", '["HOT","ICE"]', 0),
    (9,  "디카페인 바닐라라떼", 5500, "디카페인", '["HOT","ICE"]', 0),
    (10, "딸기 스무디",         5500, "스무디",  '["ICE"]',       0),
    (11, "망고 요거트 스무디",  5500, "스무디",  '["ICE"]',       0),
    (12, "블루베리 스무디",     5500, "스무디",  '["ICE"]',       0),
    (13, "레몬 에이드",         4500, "에이드",  '["ICE"]',       0),
    (14, "자몽 에이드",         4500, "에이드",  '["ICE"]',       0),
    (15, "청포도 에이드",       4500, "에이드",  '["ICE"]',       0),
    (16, "오렌지 주스",         4000, "주스",    '["ICE"]',       0),
    (17, "망고 주스",           4500, "주스",    '["ICE"]',       0),
    (18, "딸기 바나나 주스",    4500, "주스",    '["ICE"]',       0),
    (19, "얼그레이",            3000, "티",      '["HOT","ICE"]', 0),
    (20, "캐모마일",            3000, "티",      '["HOT","ICE"]', 0),
    (21, "페퍼민트",            3000, "티",      '["HOT","ICE"]', 0),
    (22, "히비스커스",          3000, "티",      '["HOT","ICE"]', 0),
]

DEFAULT_SIZES = ["S", "M", "L"]
INITIAL_MENU_ATTRS = {
    "아메리카노":          (True,  ["쌉쌀", "산미", "깔끔"]),
    "카페라떼":            (True,  ["고소", "부드러운"]),
    "카푸치노":            (True,  ["고소", "부드러운", "진한"]),
    "바닐라라떼":          (True,  ["달콤", "부드러운"]),
    "카라멜마키아토":      (True,  ["달콤", "진한"]),
    "에스프레소":          (True,  ["진한", "쌉쌀", "산미"]),
    "디카페인 아메리카노": (False, ["쌉쌀", "깔끔"]),
    "디카페인 라떼":       (False, ["고소", "부드러운"]),
    "디카페인 바닐라라떼": (False, ["달콤", "부드러운"]),
    "딸기 스무디":         (False, ["달콤", "상큼", "과일"]),
    "망고 요거트 스무디":  (False, ["달콤", "상큼", "과일", "부드러운"]),
    "블루베리 스무디":     (False, ["달콤", "상큼", "과일"]),
    "레몬 에이드":         (False, ["상큼", "탄산", "과일"]),
    "자몽 에이드":         (False, ["상큼", "쌉쌀", "탄산", "과일"]),
    "청포도 에이드":       (False, ["상큼", "달콤", "탄산", "과일"]),
    "오렌지 주스":         (False, ["상큼", "달콤", "과일"]),
    "망고 주스":           (False, ["달콤", "과일"]),
    "딸기 바나나 주스":    (False, ["달콤", "과일", "부드러운"]),
    "얼그레이":            (True,  ["향긋", "깔끔"]),
    "캐모마일":            (False, ["향긋", "부드러운"]),
    "페퍼민트":            (False, ["향긋", "상쾌"]),
    "히비스커스":          (False, ["상큼", "향긋"]),
}


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS menus (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                price       INTEGER NOT NULL,
                category    TEXT    NOT NULL,
                temps       TEXT    NOT NULL DEFAULT '[]',
                sold_out    INTEGER NOT NULL DEFAULT 0,
                image_url   TEXT,
                caffeine    INTEGER NOT NULL DEFAULT 1,
                tags        TEXT    NOT NULL DEFAULT '[]',
                sizes       TEXT    NOT NULL DEFAULT '[]',
                created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_method  TEXT    NOT NULL,
                total_amount    INTEGER NOT NULL,
                discount_amount INTEGER NOT NULL DEFAULT 0,
                final_amount    INTEGER NOT NULL,
                is_packaging    INTEGER NOT NULL DEFAULT 0,
                request_id      TEXT,
                created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                menu_name   TEXT    NOT NULL,
                temperature TEXT    NOT NULL DEFAULT '',
                quantity    INTEGER NOT NULL DEFAULT 1,
                unit_price  INTEGER NOT NULL,
                is_free     INTEGER NOT NULL DEFAULT 0,
                category    TEXT,
                options     TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS admins (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                username       TEXT    NOT NULL UNIQUE,
                password_hash  TEXT    NOT NULL,
                created_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS discounts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT    NOT NULL,
                method_code    TEXT    NOT NULL,
                description    TEXT    NOT NULL DEFAULT '',
                active         INTEGER NOT NULL DEFAULT 1,
                image_url      TEXT,
                created_at     TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            );
        """)

        discount_columns = {row["name"] for row in conn.execute("PRAGMA table_info(discounts)")}
        if "image_url" not in discount_columns:
            conn.execute("ALTER TABLE discounts ADD COLUMN image_url TEXT")

        existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(menus)")}
        if "image_url" not in existing_columns:
            conn.execute("ALTER TABLE menus ADD COLUMN image_url TEXT")

        attrs_added = False
        if "caffeine" not in existing_columns:
            conn.execute("ALTER TABLE menus ADD COLUMN caffeine INTEGER NOT NULL DEFAULT 1")
            attrs_added = True
        if "tags" not in existing_columns:
            conn.execute("ALTER TABLE menus ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
            attrs_added = True
        if "sizes" not in existing_columns:
            conn.execute("ALTER TABLE menus ADD COLUMN sizes TEXT NOT NULL DEFAULT '[]'")
            attrs_added = True

        order_columns = {row["name"] for row in conn.execute("PRAGMA table_info(orders)")}
        if "request_id" not in order_columns:
            conn.execute("ALTER TABLE orders ADD COLUMN request_id TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_request_id "
            "ON orders(request_id) WHERE request_id IS NOT NULL"
        )

        if "status" not in order_columns:
            conn.execute("ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'PAID'")
        if "status_updated_at" not in order_columns:
            conn.execute("ALTER TABLE orders ADD COLUMN status_updated_at TEXT")

        if "stock" not in existing_columns:
            conn.execute("ALTER TABLE menus ADD COLUMN stock INTEGER")

        item_columns = {row["name"] for row in conn.execute("PRAGMA table_info(order_items)")}
        if "category" not in item_columns:
            conn.execute("ALTER TABLE order_items ADD COLUMN category TEXT")
        if "options" not in item_columns:
            conn.execute("ALTER TABLE order_items ADD COLUMN options TEXT NOT NULL DEFAULT ''")
        conn.execute(
            """UPDATE order_items
               SET category = (SELECT m.category FROM menus m WHERE m.name = order_items.menu_name)
               WHERE category IS NULL"""
        )

        count = conn.execute("SELECT COUNT(*) FROM menus").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO menus (id, name, price, category, temps, sold_out) VALUES (?,?,?,?,?,?)",
                INITIAL_MENUS,
            )
            attrs_added = True

        if attrs_added:
            for name, (caffeine, tags) in INITIAL_MENU_ATTRS.items():
                conn.execute(
                    "UPDATE menus SET caffeine=?, tags=?, sizes=? WHERE name=?",
                    (int(caffeine), json.dumps(tags, ensure_ascii=False),
                     json.dumps(DEFAULT_SIZES), name),
                )

        admin_count = conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
        if admin_count == 0:
            bootstrap_username = os.getenv("ADMIN_USERNAME")
            bootstrap_hash = os.getenv("ADMIN_PASSWORD_HASH")
            if bootstrap_username and bootstrap_hash:
                conn.execute(
                    "INSERT INTO admins (username, password_hash) VALUES (?,?)",
                    (bootstrap_username, bootstrap_hash),
                )

        discount_count = conn.execute("SELECT COUNT(*) FROM discounts").fetchone()[0]
        if discount_count == 0:
            conn.executemany(
                "INSERT INTO discounts (name, method_code, description) VALUES (?,?,?)",
                INITIAL_DISCOUNTS,
            )


def get_menus() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM menus ORDER BY id").fetchall()
    return [_menu_row(r) for r in rows]


def create_menu(
    name: str,
    price: int,
    category: str,
    temps: list[str],
    image_url: str | None = None,
    caffeine: bool = True,
    tags: list[str] | None = None,
    sizes: list[str] | None = None,
    stock: int | None = None,
) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO menus (name, price, category, temps, image_url, caffeine, tags, sizes, stock, sold_out) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (name, price, category, json.dumps(temps, ensure_ascii=False), image_url,
             int(caffeine), json.dumps(tags or [], ensure_ascii=False),
             json.dumps(sizes if sizes is not None else DEFAULT_SIZES),
             stock, int(stock is not None and stock <= 0)),
        )
        row = conn.execute("SELECT * FROM menus WHERE id=?", (cur.lastrowid,)).fetchone()
    return _menu_row(row)


def update_menu(menu_id: int, **fields) -> dict | None:
    allowed = {"name", "price", "category", "temps", "sold_out", "image_url", "caffeine", "tags", "sizes", "stock"}
    clear_stock = bool(fields.pop("clear_stock", False))
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if clear_stock:
        updates.pop("stock", None)
    if not updates and not clear_stock:
        return None
    for key in ("temps", "tags", "sizes"):
        if key in updates:
            updates[key] = json.dumps(updates[key], ensure_ascii=False)
    if "caffeine" in updates:
        updates["caffeine"] = int(updates["caffeine"])
    if "sold_out" in updates:
        updates["sold_out"] = int(updates["sold_out"])
    with get_conn() as conn:
        if clear_stock:
            conn.execute("UPDATE menus SET stock=NULL WHERE id=?", (menu_id,))
        if "stock" in updates:
            updates["stock"] = max(0, int(updates["stock"]))
            before = conn.execute("SELECT stock, sold_out FROM menus WHERE id=?", (menu_id,)).fetchone()
            if updates["stock"] == 0:
                updates["sold_out"] = 1
            elif before and before["stock"] == 0 and before["sold_out"] and "sold_out" not in updates:
                updates["sold_out"] = 0
        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE menus SET {set_clause} WHERE id=?", (*updates.values(), menu_id))
        row = conn.execute("SELECT * FROM menus WHERE id=?", (menu_id,)).fetchone()
    return _menu_row(row) if row else None


def menu_name_exists(name: str, exclude_id: int | None = None) -> bool:
    normalized = name.replace(" ", "").lower()
    with get_conn() as conn:
        rows = conn.execute("SELECT id, name FROM menus").fetchall()
    return any(
        r["name"].replace(" ", "").lower() == normalized and r["id"] != exclude_id
        for r in rows
    )


def get_menu(menu_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM menus WHERE id=?", (menu_id,)).fetchone()
    return _menu_row(row) if row else None


def delete_menu(menu_id: int) -> bool:
    with get_conn() as conn:
        affected = conn.execute("DELETE FROM menus WHERE id=?", (menu_id,)).rowcount
    return affected > 0


def _menu_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["temps"] = json.loads(d["temps"])
    d["sold_out"] = bool(d["sold_out"])
    d["caffeine"] = bool(d.get("caffeine", 1))
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["sizes"] = json.loads(d.get("sizes") or "[]")
    d["stock"] = d.get("stock")
    d["track_stock"] = d["stock"] is not None
    return d


def get_discounts(active_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM discounts"
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY id"
    with get_conn() as conn:
        rows = conn.execute(sql).fetchall()
    return [_discount_row(r) for r in rows]


def get_discount(discount_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM discounts WHERE id=?", (discount_id,)).fetchone()
    return _discount_row(row) if row else None


def create_discount(
    name: str, method_code: str, description: str, active: bool = True, image_url: str | None = None
) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO discounts (name, method_code, description, active, image_url) VALUES (?,?,?,?,?)",
            (name, method_code, description, int(active), image_url),
        )
        row = conn.execute("SELECT * FROM discounts WHERE id=?", (cur.lastrowid,)).fetchone()
    return _discount_row(row)


def update_discount(discount_id: int, **fields) -> dict | None:
    allowed = {"name", "method_code", "description", "active", "image_url"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return None
    if "active" in updates:
        updates["active"] = int(updates["active"])
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE discounts SET {set_clause} WHERE id=?",
            (*updates.values(), discount_id),
        )
        row = conn.execute("SELECT * FROM discounts WHERE id=?", (discount_id,)).fetchone()
    return _discount_row(row) if row else None


def delete_discount(discount_id: int) -> bool:
    with get_conn() as conn:
        affected = conn.execute("DELETE FROM discounts WHERE id=?", (discount_id,)).rowcount
    return affected > 0


def _discount_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["active"] = bool(d["active"])
    return d


def get_admin_by_username(username: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM admins WHERE username=?", (username,)).fetchone()
    return dict(row) if row else None


def create_admin(username: str, password_hash: str) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO admins (username, password_hash) VALUES (?,?)",
            (username, password_hash),
        )
        row = conn.execute("SELECT * FROM admins WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row)


class OutOfStock(Exception):
    def __init__(self, names: list[str]):
        super().__init__(", ".join(names))
        self.names = names


def _need_by_menu(items: list[dict]) -> dict[str, int]:
    need: dict[str, int] = {}
    for i in items:
        if i.get("is_free"):
            continue
        need[i["menu_name"]] = need.get(i["menu_name"], 0) + i["quantity"]
    return need


def _check_stock(conn: sqlite3.Connection, items: list[dict]) -> None:
    short = []
    for name, qty in _need_by_menu(items).items():
        row = conn.execute("SELECT stock, sold_out FROM menus WHERE name=?", (name,)).fetchone()
        if row is None:
            continue
        if row["sold_out"] or (row["stock"] is not None and row["stock"] < qty):
            short.append(name)
    if short:
        raise OutOfStock(short)


def _apply_stock(conn: sqlite3.Connection, items: list[dict], sign: int) -> None:
    for name, qty in _need_by_menu(items).items():
        row = conn.execute("SELECT stock, sold_out FROM menus WHERE name=?", (name,)).fetchone()
        if row is None or row["stock"] is None:
            continue
        new_stock = max(0, row["stock"] + sign * qty)
        sold_out = row["sold_out"]
        if new_stock == 0:
            sold_out = 1
        elif row["stock"] == 0 and sign > 0:
            sold_out = 0
        conn.execute("UPDATE menus SET stock=?, sold_out=? WHERE name=?", (new_stock, sold_out, name))


def save_order(
    payment_method: str,
    total_amount: int,
    discount_amount: int,
    final_amount: int,
    is_packaging: bool,
    items: list[dict],
    request_id: str | None = None,
) -> dict:
    with get_conn() as conn:
        if request_id:
            existing = conn.execute(
                "SELECT * FROM orders WHERE request_id=?", (request_id,)
            ).fetchone()
            if existing:
                return dict(existing)
        _check_stock(conn, items)
        try:
            cur = conn.execute(
                """INSERT INTO orders
                   (payment_method, total_amount, discount_amount, final_amount, is_packaging, request_id)
                   VALUES (?,?,?,?,?,?)""",
                (payment_method, total_amount, discount_amount, final_amount,
                 int(is_packaging), request_id),
            )
        except sqlite3.IntegrityError:
            existing = conn.execute(
                "SELECT * FROM orders WHERE request_id=?", (request_id,)
            ).fetchone()
            if existing:
                return dict(existing)
            raise
        order_id = cur.lastrowid
        _apply_stock(conn, items, sign=-1)
        category_by_name = {
            r["name"]: r["category"] for r in conn.execute("SELECT name, category FROM menus")
        }
        conn.executemany(
            """INSERT INTO order_items
               (order_id, menu_name, temperature, quantity, unit_price, is_free, category, options)
               VALUES (?,?,?,?,?,?,?,?)""",
            [
                (order_id, i["menu_name"], i.get("temperature", ""),
                 i["quantity"], i["unit_price"], int(i.get("is_free", False)),
                 category_by_name.get(i["menu_name"]), (i.get("options") or "")[:200])
                for i in items
            ],
        )
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    return dict(row)

ORDER_STATUSES = ("PAID", "CANCELLED")


def get_order(order_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            return None
        order = dict(row)
        order["items"] = [dict(r) for r in conn.execute(
            "SELECT * FROM order_items WHERE order_id=?", (order_id,))]
    return order


def change_order_status(order_id: int, new_status: str) -> tuple[dict | None, str | None]:
    if new_status not in ORDER_STATUSES:
        return None, "알 수 없는 주문 상태입니다."
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            return None, "주문을 찾을 수 없습니다."
        current = row["status"]
        if new_status == current:
            return get_order(order_id), None
        if current == "CANCELLED":
            return None, "이미 취소된 주문입니다."
        if new_status == "PAID":
            return None, "취소된 주문은 되돌릴 수 없습니다."
        conn.execute(
            "UPDATE orders SET status=?, status_updated_at=datetime('now','localtime') WHERE id=?",
            (new_status, order_id),
        )
        items = [dict(r) for r in conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,))]
        _apply_stock(conn, [{"menu_name": i["menu_name"], "quantity": i["quantity"],
                             "is_free": i["is_free"]} for i in items], sign=+1)
    return get_order(order_id), None


def get_orders(date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    sql = "SELECT * FROM orders"
    params: list = []
    if date_from:
        sql += " WHERE created_at >= ?"
        params.append(date_from)
    if date_to:
        sql += (" AND" if date_from else " WHERE") + " created_at <= ?"
        params.append(date_to)
    sql += " ORDER BY created_at DESC"

    with get_conn() as conn:
        orders = [dict(r) for r in conn.execute(sql, params).fetchall()]
        for o in orders:
            o["items"] = [
                dict(r) for r in
                conn.execute(
                    "SELECT * FROM order_items WHERE order_id=?", (o["id"],)
                ).fetchall()
            ]
    return orders


def _period_range(period: str) -> tuple[str, str, str, str]:
    now = datetime.now()
    fmt = "%Y-%m-%d %H:%M:%S"

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
        prev_start = start - timedelta(days=1)
        prev_end = start
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
        prev_start = start - timedelta(weeks=1)
        prev_end = start
    else:
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
        prev_start = (start - timedelta(days=1)).replace(day=1, hour=0, minute=0, second=0)
        prev_end = start

    return start.strftime(fmt), end.strftime(fmt), prev_start.strftime(fmt), prev_end.strftime(fmt)


def _aggregate(conn: sqlite3.Connection, start: str, end: str) -> dict:
    row = conn.execute(
        """SELECT
               COUNT(*)                   AS orders,
               COALESCE(SUM(final_amount),0) AS sales,
               COALESCE(AVG(final_amount),0) AS avg,
               COALESCE(SUM(CASE WHEN discount_amount > 0 THEN 1 ELSE 0 END),0) AS coupons
           FROM orders WHERE created_at >= ? AND created_at <= ? AND status != 'CANCELLED'""",
        (start, end),
    ).fetchone()
    return {
        "orders": row["orders"],
        "sales": row["sales"],
        "avg": int(row["avg"]),
        "coupons": row["coupons"],
    }


def get_sales(period: str) -> dict:
    start, end, prev_start, prev_end = _period_range(period)
    with get_conn() as conn:
        curr = _aggregate(conn, start, end)
        prev = _aggregate(conn, prev_start, prev_end)
    return {"current": curr, "previous": prev}

WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]


def get_sales_trend(period: str) -> list[dict]:
    start, end, _, _ = _period_range(period)
    start_dt = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")

    if period == "today":
        bucket_sql = "strftime('%H', created_at)"
        buckets = [f"{h:02d}" for h in range(24)]
        labels = {b: (f"{int(b)}시", f"{int(b)}시~{int(b) + 1}시") for b in buckets}
    else:
        bucket_sql = "strftime('%Y-%m-%d', created_at)"
        if period == "week":
            days = [start_dt.date() + timedelta(days=i) for i in range(7)]
        else:
            first = start_dt.date().replace(day=1)
            next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
            days = [first + timedelta(days=i) for i in range((next_month - first).days)]
        buckets = [d.isoformat() for d in days]
        labels = {
            d.isoformat(): (
                WEEKDAYS_KO[d.weekday()] if period == "week" else f"{d.day}일",
                f"{d.month}월 {d.day}일 ({WEEKDAYS_KO[d.weekday()]})",
            )
            for d in days
        }

    with get_conn() as conn:
        rows = conn.execute(
            f"""SELECT {bucket_sql} AS bucket,
                       COALESCE(SUM(final_amount),0) AS sales,
                       COUNT(*) AS orders
                FROM orders
                WHERE created_at >= ? AND created_at <= ? AND status != 'CANCELLED'
                GROUP BY bucket""",
            (start, end),
        ).fetchall()
    by_bucket = {r["bucket"]: r for r in rows}

    return [
        {
            "label": labels[b][0],
            "title": labels[b][1],
            "sales": by_bucket[b]["sales"] if b in by_bucket else 0,
            "orders": by_bucket[b]["orders"] if b in by_bucket else 0,
        }
        for b in buckets
    ]


def get_analytics() -> dict:
    now = datetime.now()
    week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    with get_conn() as conn:
        top_rows = conn.execute(
            """SELECT oi.menu_name, SUM(oi.quantity) AS cnt
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               WHERE o.created_at >= ? AND oi.is_free = 0 AND o.status != 'CANCELLED'
               GROUP BY oi.menu_name
               ORDER BY cnt DESC LIMIT 5""",
            (week_start,),
        ).fetchall()

        cat_rows = conn.execute(
            """SELECT COALESCE(oi.category, m.category, '기타') AS category, SUM(oi.quantity) AS cnt
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               LEFT JOIN menus m ON m.name = oi.menu_name
               WHERE o.created_at >= ? AND oi.is_free = 0 AND o.status != 'CANCELLED'
               GROUP BY COALESCE(oi.category, m.category, '기타')""",
            (week_start,),
        ).fetchall()

        cat_sales_rows = conn.execute(
            """SELECT COALESCE(oi.category, m.category, '기타') AS category,
                      SUM(oi.quantity * oi.unit_price) AS amount,
                      SUM(oi.quantity) AS cnt
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               LEFT JOIN menus m ON m.name = oi.menu_name
               WHERE o.created_at >= ? AND oi.is_free = 0 AND o.status != 'CANCELLED'
               GROUP BY COALESCE(oi.category, m.category, '기타')
               ORDER BY amount DESC""",
            (week_start,),
        ).fetchall()

        temp_rows = conn.execute(
            """SELECT oi.temperature, SUM(oi.quantity) AS cnt
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               WHERE o.created_at >= ? AND oi.is_free = 0 AND o.status != 'CANCELLED'
                 AND oi.temperature IN ('HOT','ICE')
               GROUP BY oi.temperature""",
            (week_start,),
        ).fetchall()

        time_rows = conn.execute(
            """SELECT
                   CASE
                       WHEN CAST(strftime('%H', o.created_at) AS INTEGER) BETWEEN 8  AND 11 THEN '오전 (08~12시)'
                       WHEN CAST(strftime('%H', o.created_at) AS INTEGER) BETWEEN 12 AND 13 THEN '점심 (12~14시)'
                       WHEN CAST(strftime('%H', o.created_at) AS INTEGER) BETWEEN 14 AND 16 THEN '오후 (14~17시)'
                       ELSE '저녁 (17~22시)'
                   END AS time_slot,
                   oi.menu_name,
                   SUM(oi.quantity) AS cnt
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               WHERE o.created_at >= ? AND oi.is_free = 0 AND o.status != 'CANCELLED'
               GROUP BY time_slot, oi.menu_name
               ORDER BY time_slot, cnt DESC""",
            (week_start,),
        ).fetchall()

    top_menus = [{"name": r["menu_name"], "count": r["cnt"]} for r in top_rows]

    total_cat = sum(r["cnt"] for r in cat_rows) or 1
    category_data = [
        {"name": r["category"], "value": round(r["cnt"] / total_cat * 100)}
        for r in cat_rows
    ]

    total_temp = sum(r["cnt"] for r in temp_rows) or 1
    temp_data = [
        {"name": r["temperature"], "value": round(r["cnt"] / total_temp * 100)}
        for r in temp_rows
    ]

    time_map: dict[str, list[str]] = {}
    for r in time_rows:
        time_map.setdefault(r["time_slot"], []).append(r["menu_name"])

    time_slots = ["오전 (08~12시)", "점심 (12~14시)", "오후 (14~17시)", "저녁 (17~22시)"]
    time_menus = [
        {
            "time": slot,
            "top": time_map.get(slot, ["—"])[0],
            "second": time_map.get(slot, ["—", "—"])[1] if len(time_map.get(slot, [])) > 1 else "—",
        }
        for slot in time_slots
    ]

    total_amount = sum(r["amount"] for r in cat_sales_rows) or 1
    category_sales = [
        {"name": r["category"], "amount": r["amount"], "count": r["cnt"],
         "share": round(r["amount"] / total_amount * 100)}
        for r in cat_sales_rows
    ]

    return {
        "category_sales": category_sales,
        "top_menus": top_menus,
        "category_data": category_data,
        "temp_data": temp_data,
        "time_menus": time_menus,
    }

init_db()
