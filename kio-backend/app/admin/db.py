import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "kio_admin.db"

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
                created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS orders (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_method  TEXT    NOT NULL,
                total_amount    INTEGER NOT NULL,
                discount_amount INTEGER NOT NULL DEFAULT 0,
                final_amount    INTEGER NOT NULL,
                is_packaging    INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id    INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                menu_name   TEXT    NOT NULL,
                temperature TEXT    NOT NULL DEFAULT '',
                quantity    INTEGER NOT NULL DEFAULT 1,
                unit_price  INTEGER NOT NULL,
                is_free     INTEGER NOT NULL DEFAULT 0
            );
        """)

        count = conn.execute("SELECT COUNT(*) FROM menus").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO menus (id, name, price, category, temps, sold_out) VALUES (?,?,?,?,?,?)",
                INITIAL_MENUS,
            )


# ── Menus ──────────────────────────────────────────────────────────────────

def get_menus() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM menus ORDER BY id").fetchall()
    return [_menu_row(r) for r in rows]


def create_menu(name: str, price: int, category: str, temps: list[str]) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO menus (name, price, category, temps) VALUES (?,?,?,?)",
            (name, price, category, json.dumps(temps, ensure_ascii=False)),
        )
        row = conn.execute("SELECT * FROM menus WHERE id=?", (cur.lastrowid,)).fetchone()
    return _menu_row(row)


def update_menu(menu_id: int, **fields) -> dict | None:
    allowed = {"name", "price", "category", "temps", "sold_out"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return None
    if "temps" in updates:
        updates["temps"] = json.dumps(updates["temps"], ensure_ascii=False)
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE menus SET {set_clause} WHERE id=?",
            (*updates.values(), menu_id),
        )
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
    return d


# ── Orders ─────────────────────────────────────────────────────────────────

def save_order(
    payment_method: str,
    total_amount: int,
    discount_amount: int,
    final_amount: int,
    is_packaging: bool,
    items: list[dict],
) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO orders
               (payment_method, total_amount, discount_amount, final_amount, is_packaging)
               VALUES (?,?,?,?,?)""",
            (payment_method, total_amount, discount_amount, final_amount, int(is_packaging)),
        )
        order_id = cur.lastrowid
        conn.executemany(
            """INSERT INTO order_items
               (order_id, menu_name, temperature, quantity, unit_price, is_free)
               VALUES (?,?,?,?,?,?)""",
            [
                (order_id, i["menu_name"], i.get("temperature", ""),
                 i["quantity"], i["unit_price"], int(i.get("is_free", False)))
                for i in items
            ],
        )
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    return dict(row)


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


# ── Sales stats ────────────────────────────────────────────────────────────

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
    else:  # month
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
               SUM(CASE WHEN discount_amount > 0 THEN 1 ELSE 0 END) AS coupons
           FROM orders WHERE created_at >= ? AND created_at <= ?""",
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


# ── Analytics ──────────────────────────────────────────────────────────────

def get_analytics() -> dict:
    now = datetime.now()
    week_start = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")

    with get_conn() as conn:
        # 판매량 TOP 메뉴
        top_rows = conn.execute(
            """SELECT oi.menu_name, SUM(oi.quantity) AS cnt
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               WHERE o.created_at >= ? AND oi.is_free = 0
               GROUP BY oi.menu_name
               ORDER BY cnt DESC LIMIT 5""",
            (week_start,),
        ).fetchall()

        # 카테고리별 판매 수량
        cat_rows = conn.execute(
            """SELECT m.category, SUM(oi.quantity) AS cnt
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               JOIN menus m ON m.name = oi.menu_name
               WHERE o.created_at >= ? AND oi.is_free = 0
               GROUP BY m.category""",
            (week_start,),
        ).fetchall()

        # 온도별 비율
        temp_rows = conn.execute(
            """SELECT oi.temperature, SUM(oi.quantity) AS cnt
               FROM order_items oi
               JOIN orders o ON o.id = oi.order_id
               WHERE o.created_at >= ? AND oi.is_free = 0
                 AND oi.temperature IN ('HOT','ICE')
               GROUP BY oi.temperature""",
            (week_start,),
        ).fetchall()

        # 시간대별 인기 메뉴 (top 2)
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
               WHERE o.created_at >= ? AND oi.is_free = 0
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

    return {
        "top_menus": top_menus,
        "category_data": category_data,
        "temp_data": temp_data,
        "time_menus": time_menus,
    }


init_db()
