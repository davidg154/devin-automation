from __future__ import annotations

import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://api.devin.ai/v1"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.devin_api_key}",
        "Content-Type": "application/json",
    }


async def create_session(
    prompt: str,
    idempotency_key: Optional[str] = None,
) -> dict:
    payload: dict = {"prompt": prompt}
    if idempotency_key:
        payload["idempotency_key"] = idempotency_key

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{_BASE}/sessions", json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def get_session(session_id: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE}/session/{session_id}", headers=_headers()
        )
        resp.raise_for_status()
        return resp.json()


async def list_sessions(limit: int = 50) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_BASE}/sessions",
            params={"limit": limit},
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json().get("sessions", [])
