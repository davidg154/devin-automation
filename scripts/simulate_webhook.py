"""
Fire a fake GitHub 'issues.labeled' webhook at the local automation server.

Usage (no args = trigger all 3 issues):
    python scripts/simulate_webhook.py

Trigger a single issue:
    python scripts/simulate_webhook.py 2
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

SERVER_URL    = os.environ.get("SERVER_URL", "http://localhost:8000")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
GITHUB_REPO   = os.environ.get("GITHUB_REPO", "davidg154/superset")
TRIGGER_LABEL = os.environ.get("DEVIN_TRIGGER_LABEL", "devin-fix")

ISSUES = {
    1: {
        "title": "bug: ORDINAL_MAP in date_parser.py is incomplete — ordinals beyond 'first' silently default to 1",
        "body": "Extend ORDINAL_MAP to cover second/third/fourth/fifth and add unit tests.",
    },
    2: {
        "title": "chore: Modernize deprecated typing imports in superset/utils/json.py",
        "body": "Replace Dict/Optional/Union with built-in generics and add `from __future__ import annotations`.",
    },
    3: {
        "title": "chore: Upgrade pandas from 2.1.4 to 2.2.x",
        "body": "Update requirements/base.txt to pandas==2.2.3 and fix any deprecation warnings.",
    },
}


def _sign(payload: bytes) -> str:
    if not WEBHOOK_SECRET:
        return ""
    mac = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def fire(issue_number: int) -> None:
    issue = ISSUES[issue_number]
    payload = {
        "action": "labeled",
        "label": {"name": TRIGGER_LABEL},
        "issue": {
            "number": issue_number,
            "title": issue["title"],
            "body": issue["body"],
            "html_url": f"https://github.com/{GITHUB_REPO}/issues/{issue_number}",
        },
        "repository": {"full_name": GITHUB_REPO},
    }
    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "issues",
        "X-Hub-Signature-256": _sign(body),
    }
    resp = httpx.post(f"{SERVER_URL}/webhook", content=body, headers=headers)
    print(f"  issue #{issue_number} → {resp.status_code} {resp.text[:120]}")


def main() -> None:
    targets = [int(a) for a in sys.argv[1:]] if sys.argv[1:] else list(ISSUES)
    print(f"Firing webhooks for issues {targets} → {SERVER_URL}/webhook\n")
    for num in targets:
        fire(num)
        if num != targets[-1]:
            time.sleep(1)
    print("\nDone. Watch the dashboard: http://localhost:8000/dashboard")


if __name__ == "__main__":
    main()
