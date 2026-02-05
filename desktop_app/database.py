import sqlite3
from pathlib import Path
from datetime import datetime

DB_SCHEMA = """
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
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.executescript(DB_SCHEMA)
        self.conn.commit()

    def upsert_chat(self, chat_id: str, display_name: str, last_message_at: str) -> None:
        now = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT INTO chats(chat_id, display_name, created_at, last_message_at, unread_count)
            VALUES(?, ?, ?, ?, 0)
            ON CONFLICT(chat_id) DO UPDATE SET
                display_name=excluded.display_name,
                last_message_at=excluded.last_message_at
            """,
            (chat_id, display_name, now, last_message_at),
        )
        self.conn.commit()

    def increment_unread(self, chat_id: str) -> None:
        self.conn.execute(
            "UPDATE chats SET unread_count = unread_count + 1 WHERE chat_id = ?",
            (chat_id,),
        )
        self.conn.commit()

    def reset_unread(self, chat_id: str) -> None:
        self.conn.execute(
            "UPDATE chats SET unread_count = 0 WHERE chat_id = ?",
            (chat_id,),
        )
        self.conn.commit()

    def add_message(
        self,
        chat_id: str,
        direction: str,
        text: str,
        ts: str,
        status: str,
        meta_json: str = "",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO messages(chat_id, direction, text, ts, status, meta_json)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (chat_id, direction, text, ts, status, meta_json),
        )
        self.conn.execute(
            "UPDATE chats SET last_message_at = ? WHERE chat_id = ?",
            (ts, chat_id),
        )
        self.conn.commit()

    def list_chats(self):
        cursor = self.conn.execute(
            "SELECT chat_id, display_name, last_message_at, unread_count FROM chats ORDER BY last_message_at DESC"
        )
        return cursor.fetchall()

    def list_messages(self, chat_id: str):
        cursor = self.conn.execute(
            "SELECT direction, text, ts, status FROM messages WHERE chat_id = ? ORDER BY ts ASC",
            (chat_id,),
        )
        return cursor.fetchall()

    def add_calendar_event(
        self, chat_id: str, calendar_id: str, event_id: str, start_ts: str, end_ts: str
    ) -> None:
        created_at = datetime.utcnow().isoformat()
        self.conn.execute(
            """
            INSERT INTO calendar_events(chat_id, calendar_id, event_id, start_ts, end_ts, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (chat_id, calendar_id, event_id, start_ts, end_ts, created_at),
        )
        self.conn.commit()

    def list_calendar_events(self):
        cursor = self.conn.execute(
            "SELECT chat_id, calendar_id, event_id, start_ts, end_ts FROM calendar_events ORDER BY start_ts DESC"
        )
        return cursor.fetchall()

    def close(self) -> None:
        self.conn.close()
