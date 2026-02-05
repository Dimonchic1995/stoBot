import sqlite3
from datetime import datetime


SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT UNIQUE,
    display_name TEXT,
    created_at TEXT,
    last_message_at TEXT,
    unread_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT,
    direction TEXT,
    text TEXT,
    ts TEXT,
    status TEXT,
    meta_json TEXT
);
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT,
    calendar_id TEXT,
    event_id TEXT,
    start_ts TEXT,
    end_ts TEXT,
    created_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages(chat_id, ts);
"""


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(SCHEMA)

    def upsert_chat(self, chat_id: str, display_name: str):
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO chats(chat_id, display_name, created_at, last_message_at, unread_count)
                VALUES (?, ?, ?, ?, 0)
                ON CONFLICT(chat_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    last_message_at=excluded.last_message_at
                """,
                (chat_id, display_name, now, now),
            )

    def add_message(self, chat_id: str, direction: str, text: str, ts: str, status: str, meta_json: str = ""):
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO messages(chat_id, direction, text, ts, status, meta_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chat_id, direction, text, ts, status, meta_json),
            )
            conn.execute(
                "UPDATE chats SET last_message_at = ? WHERE chat_id = ?",
                (ts, chat_id),
            )

    def add_calendar_event(self, chat_id: str, calendar_id: str, event_id: str, start_ts: str, end_ts: str):
        now = datetime.utcnow().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO calendar_events(chat_id, calendar_id, event_id, start_ts, end_ts, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chat_id, calendar_id, event_id, start_ts, end_ts, now),
            )

    def get_chats(self):
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT chat_id, display_name, last_message_at, unread_count FROM chats ORDER BY last_message_at DESC"
            ).fetchall()
        return rows

    def get_messages(self, chat_id: str):
        with self._get_conn() as conn:
            rows = conn.execute(
                """
                SELECT direction, text, ts, status FROM messages
                WHERE chat_id = ?
                ORDER BY ts ASC
                """,
                (chat_id,),
            ).fetchall()
        return rows
