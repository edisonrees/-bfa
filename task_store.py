"""
SQLite-backed task snapshot store.

Keeps UI polls consistent across threads and process restarts.
Password payloads for huge lists stay on disk (wordlist_path); snapshots
store progress / hits / recent results only.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config import config

_LOCK = threading.RLock()
_DB_PATH = os.path.join(config.UPLOAD_FOLDER, "mocka_tasks.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()
        finally:
            conn.close()


def save_snapshot(task_id: str, payload: Dict[str, Any]) -> None:
    """Persist a JSON-safe task snapshot (no huge password arrays)."""
    slim = dict(payload)
    # never persist full password lists
    slim.pop("passwords", None)
    body = json.dumps(slim, separators=(",", ":"), default=str)
    with _LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO tasks(task_id, payload, updated_at)
                VALUES(?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    payload=excluded.payload,
                    updated_at=excluded.updated_at
                """,
                (task_id, body, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()


def load_snapshot(task_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT payload FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
            if not row:
                return None
            return json.loads(row["payload"])
        finally:
            conn.close()


def load_all_snapshots() -> List[Dict[str, Any]]:
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT payload FROM tasks ORDER BY updated_at DESC"
            ).fetchall()
            return [json.loads(r["payload"]) for r in rows]
        finally:
            conn.close()


def delete_snapshot(task_id: str) -> None:
    with _LOCK:
        conn = _connect()
        try:
            conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()
        finally:
            conn.close()


def clear_finished_snapshots(statuses=("completed", "failed", "cancelled")) -> int:
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute("SELECT task_id, payload FROM tasks").fetchall()
            removed = 0
            for row in rows:
                payload = json.loads(row["payload"])
                if payload.get("status") in statuses:
                    conn.execute("DELETE FROM tasks WHERE task_id = ?", (row["task_id"],))
                    removed += 1
            conn.commit()
            return removed
        finally:
            conn.close()


init_db()
