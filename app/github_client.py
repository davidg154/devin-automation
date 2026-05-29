from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE = "https://api.github.com"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"token {settings.github_token}",
        "Accept": "application/vnd.github.v3+json",
    }


async def post_comment(repo: str, issue_number: int, body: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_BASE}/repos/{repo}/issues/{issue_number}/comments",
            json={"body": body},
            headers=_headers(),
        )
        resp.raise_for_status()
        logger.info("Posted comment on %s#%d", repo, issue_number)


async def add_label(repo: str, issue_number: int, label: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_BASE}/repos/{repo}/issues/{issue_number}/labels",
            json={"labels": [label]},
            headers=_headers(),
        )
        resp.raise_for_status()
