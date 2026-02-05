import json
import sqlite3
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT UNIQUE,
                display_name TEXT,
                created_at TEXT,
                last_message_at TEXT,
                unread_count INTEGER DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                direction TEXT,
                text TEXT,
                ts TEXT,
                status TEXT,
                meta_json TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS calendar_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                calendar_id TEXT,
                event_id TEXT,
                start_ts TEXT,
                end_ts TEXT,
                created_at TEXT
            )
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_ts
            ON messages(chat_id, ts)
            """
        )
        self._conn.commit()

    def ensure_chat(self, chat_id: str, display_name: str, created_at: str) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO chats(chat_id, display_name, created_at, last_message_at, unread_count)
            VALUES(?, ?, ?, ?, 0)
            ON CONFLICT(chat_id) DO UPDATE SET display_name=excluded.display_name
            """,
            (chat_id, display_name, created_at, created_at),
        )
        self._conn.commit()

    def add_message(
        self,
        chat_id: str,
        direction: str,
        text: str,
        ts: str,
        status: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        meta_json = json.dumps(meta or {}, ensure_ascii=False)
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO messages(chat_id, direction, text, ts, status, meta_json)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (chat_id, direction, text, ts, status, meta_json),
        )
        if direction == "in":
            cur.execute(
                """
                UPDATE chats
                SET last_message_at=?, unread_count=unread_count + 1
                WHERE chat_id=?
                """,
                (ts, chat_id),
            )
        else:
            cur.execute(
                """
                UPDATE chats
                SET last_message_at=?
                WHERE chat_id=?
                """,
                (ts, chat_id),
            )
        self._conn.commit()

    def add_calendar_event(
        self,
        chat_id: str,
        calendar_id: str,
        event_id: str,
        start_ts: str,
        end_ts: str,
        created_at: str,
    ) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO calendar_events(chat_id, calendar_id, event_id, start_ts, end_ts, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (chat_id, calendar_id, event_id, start_ts, end_ts, created_at),
        )
        self._conn.commit()

    def get_chats(self) -> list[sqlite3.Row]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT chat_id, display_name, last_message_at, unread_count
            FROM chats
            ORDER BY last_message_at DESC
            """
        )
        return cur.fetchall()

    def reset_unread(self, chat_id: str) -> None:
        cur = self._conn.cursor()
        cur.execute("UPDATE chats SET unread_count=0 WHERE chat_id=?", (chat_id,))
        self._conn.commit()

    def get_messages(self, chat_id: str) -> list[sqlite3.Row]:
        cur = self._conn.cursor()
        cur.execute(
            """
            SELECT direction, text, ts, status, meta_json
            FROM messages
            WHERE chat_id=?
            ORDER BY ts ASC
            """,
            (chat_id,),
        )
        return cur.fetchall()
