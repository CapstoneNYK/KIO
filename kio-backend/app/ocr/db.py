import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "kio_ocr.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS screens (
                id           INTEGER PRIMARY KEY,
                screen_name  TEXT UNIQUE NOT NULL,
                captured_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS elements (
                id        INTEGER PRIMARY KEY,
                screen_id INTEGER NOT NULL REFERENCES screens(id) ON DELETE CASCADE,
                text      TEXT NOT NULL,
                label     TEXT NOT NULL,
                x1        INTEGER, y1 INTEGER,
                x2        INTEGER, y2 INTEGER,
                confidence REAL
            );
        """)


def save_screen(screen_name: str, elements: list[dict]):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM screens WHERE screen_name = ?", (screen_name,))
        cur = conn.execute(
            "INSERT INTO screens (screen_name) VALUES (?)", (screen_name,)
        )
        screen_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO elements (screen_id, text, label, x1, y1, x2, y2, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (screen_id, e["text"], e["label"],
                 e["box"][0], e["box"][1], e["box"][2], e["box"][3],
                 e["confidence"])
                for e in elements
            ],
        )


def query_text(text: str) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT s.screen_name, e.text, e.label,
                   e.x1, e.y1, e.x2, e.y2, e.confidence
            FROM elements e
            JOIN screens s ON e.screen_id = s.id
            WHERE e.text LIKE ?
            ORDER BY e.confidence DESC
            LIMIT 10
            """,
            (f"%{text}%",),
        ).fetchall()
        return [dict(r) for r in rows]


def get_screens() -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT screen_name, captured_at FROM screens ORDER BY captured_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_menu_texts() -> list[str]:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT DISTINCT text FROM elements WHERE label = 'menu_item' ORDER BY text"
        ).fetchall()
        return [r[0] for r in rows]
