import sqlite3
from pathlib import Path
from typing import Iterable, Optional


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
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def upsert_chat(self, chat_id: str, display_name: str, ts: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO chats (chat_id, display_name, created_at, last_message_at, unread_count)
                VALUES (?, ?, ?, ?, 0)
                ON CONFLICT(chat_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    last_message_at=excluded.last_message_at
                """,
                (chat_id, display_name, ts, ts),
            )

    def update_unread(self, chat_id: str, count: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE chats SET unread_count = ? WHERE chat_id = ?",
                (count, chat_id),
            )

    def add_message(
        self,
        chat_id: str,
        direction: str,
        text: str,
        ts: str,
        status: Optional[str] = None,
        meta_json: Optional[str] = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (chat_id, direction, text, ts, status, meta_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chat_id, direction, text, ts, status, meta_json),
            )

    def list_chats(self) -> Iterable[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM chats ORDER BY last_message_at DESC"
            ).fetchall()

    def get_chat(self, chat_id: str) -> Optional[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM chats WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()

    def increment_unread(self, chat_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE chats SET unread_count = unread_count + 1 WHERE chat_id = ?",
                (chat_id,),
            )

    def list_messages(self, chat_id: str) -> Iterable[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM messages WHERE chat_id = ? ORDER BY ts ASC",
                (chat_id,),
            ).fetchall()

    def add_calendar_event(
        self,
        chat_id: str,
        calendar_id: str,
        event_id: str,
        start_ts: str,
        end_ts: str,
        created_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO calendar_events (chat_id, calendar_id, event_id, start_ts, end_ts, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (chat_id, calendar_id, event_id, start_ts, end_ts, created_at),
            )
