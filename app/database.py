from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

import aiosqlite

from app.config import settings

_DB = settings.database_path


async def init_db() -> None:
    os.makedirs(os.path.dirname(_DB) or ".", exist_ok=True)
    async with aiosqlite.connect(_DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id   TEXT PRIMARY KEY,
                issue_number INTEGER NOT NULL,
                issue_title  TEXT    NOT NULL,
                repo         TEXT    NOT NULL,
                status       TEXT    NOT NULL DEFAULT 'running',
                devin_url    TEXT,
                pr_url       TEXT,
                created_at   TEXT    NOT NULL,
                updated_at   TEXT    NOT NULL,
                completed_at TEXT
            )
        """)
        await db.commit()


async def insert_session(
    session_id: str,
    issue_number: int,
    issue_title: str,
    repo: str,
    devin_url: Optional[str] = None,
) -> None:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            """INSERT OR IGNORE INTO sessions
               (session_id, issue_number, issue_title, repo, status, devin_url,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, 'running', ?, ?, ?)""",
            (session_id, issue_number, issue_title, repo, devin_url, now, now),
        )
        await db.commit()


async def update_session(
    session_id: str,
    status: str,
    pr_url: Optional[str] = None,
) -> None:
    now = datetime.utcnow().isoformat()
    completed_at = now if status in ("completed", "failed") else None
    async with aiosqlite.connect(_DB) as db:
        await db.execute(
            """UPDATE sessions
               SET status=?, pr_url=COALESCE(?, pr_url), updated_at=?,
                   completed_at=COALESCE(completed_at, ?)
               WHERE session_id=?""",
            (status, pr_url, now, completed_at, session_id),
        )
        await db.commit()


async def get_pending_sessions() -> list[dict]:
    async with aiosqlite.connect(_DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE status IN ('running', 'pending')"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_sessions() -> list[dict]:
    async with aiosqlite.connect(_DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
