import sqlite3
import os
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "streetsense.db"


def get_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS delivery_notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            address_id  TEXT NOT NULL,
            address_text TEXT NOT NULL,
            driver_id   TEXT NOT NULL,
            driver_name TEXT NOT NULL,
            status      TEXT NOT NULL,
            note_text   TEXT NOT NULL,
            timestamp   TEXT NOT NULL,
            cognified   INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS address_meta (
            address_id      TEXT PRIMARY KEY,
            address_text    TEXT NOT NULL,
            conflicts       INTEGER DEFAULT 0,
            last_cognified  TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_notes_address ON delivery_notes(address_id);
        CREATE INDEX IF NOT EXISTS idx_notes_timestamp ON delivery_notes(timestamp);
    """)
    conn.commit()
    conn.close()


def insert_note(note: dict) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO delivery_notes
           (address_id, address_text, driver_id, driver_name, status, note_text, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            note["address_id"],
            note["address_text"],
            note["driver_id"],
            note["driver_name"],
            note["status"],
            note["note_text"],
            note["timestamp"],
        ),
    )
    note_id = c.lastrowid

    c.execute(
        """INSERT INTO address_meta (address_id, address_text)
           VALUES (?, ?)
           ON CONFLICT(address_id) DO UPDATE SET address_text=excluded.address_text""",
        (note["address_id"], note["address_text"]),
    )
    conn.commit()
    conn.close()
    return note_id


def get_notes_for_address(address_id: str) -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    rows = c.execute(
        "SELECT * FROM delivery_notes WHERE address_id=? ORDER BY timestamp DESC",
        (address_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_address_stats() -> list[dict]:
    conn = get_conn()
    c = conn.cursor()
    rows = c.execute("""
        SELECT
            n.address_id,
            n.address_text,
            COUNT(*)                                        AS total,
            SUM(CASE WHEN n.status='FAILED' THEN 1 ELSE 0 END) AS failed,
            MAX(n.timestamp)                                AS last_delivery,
            COALESCE(m.conflicts, 0)                        AS conflicts
        FROM delivery_notes n
        LEFT JOIN address_meta m ON m.address_id = n.address_id
        GROUP BY n.address_id
        ORDER BY failed DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_conflict(address_id: str, delta: int = 1):
    conn = get_conn()
    conn.execute(
        "UPDATE address_meta SET conflicts = conflicts + ? WHERE address_id = ?",
        (delta, address_id),
    )
    conn.commit()
    conn.close()


def update_cognified(address_id: str):
    conn = get_conn()
    conn.execute(
        "UPDATE address_meta SET last_cognified=? WHERE address_id=?",
        (datetime.utcnow().isoformat(), address_id),
    )
    conn.execute(
        "UPDATE delivery_notes SET cognified=1 WHERE address_id=?",
        (address_id,),
    )
    conn.commit()
    conn.close()


def purge_address(address_id: str) -> int:
    conn = get_conn()
    c = conn.cursor()
    count = c.execute(
        "SELECT COUNT(*) FROM delivery_notes WHERE address_id=?", (address_id,)
    ).fetchone()[0]
    c.execute("DELETE FROM delivery_notes WHERE address_id=?", (address_id,))
    c.execute("DELETE FROM address_meta WHERE address_id=?", (address_id,))
    conn.commit()
    conn.close()
    return count


def count_all_notes() -> int:
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM delivery_notes").fetchone()[0]
    conn.close()
    return count
