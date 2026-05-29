from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app import devin_client, github_client
from app.config import settings
from app.database import get_all_sessions, init_db, insert_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    from app.worker import poll_loop
    task = asyncio.create_task(poll_loop())
    logger.info("Devin automation started — listening for GitHub webhooks")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Devin Superset Automation", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_signature(payload: bytes, sig_header: str) -> bool:
    if not settings.webhook_secret:
        return True
    expected = "sha256=" + hmac.new(
        settings.webhook_secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


def _build_prompt(issue_number: int, title: str, body: str, repo: str) -> str:
    return f"""You are an expert Python engineer working on a fork of Apache Superset.

Repository: https://github.com/{repo}
Branch to work on: main

## Task
Resolve GitHub Issue #{issue_number}: {title}

## Issue Description
{body}

## Instructions
1. Clone/pull the repository.
2. Implement the code changes described in the issue.
3. Run the relevant unit tests to verify correctness:
   `python -m pytest tests/unit_tests/ -x -q --no-header`
4. If you introduce new logic, add or update tests.
5. Commit your changes with a descriptive message.
6. Open a pull request against the `main` branch of https://github.com/{repo}
   - Title: the issue title (keep it short and clear)
   - Body: briefly describe what changed and reference the issue with "Fixes #{issue_number}"

Do not make unrelated changes. Focus on correctness and clean, idiomatic Python.
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/webhook")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
):
    payload_bytes = await request.body()

    if not _verify_signature(payload_bytes, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if x_github_event != "issues":
        return {"status": "ignored", "event": x_github_event}

    payload = json.loads(payload_bytes)
    action = payload.get("action", "")

    if action != "labeled":
        return {"status": "ignored", "action": action}

    label_name = payload.get("label", {}).get("name", "")
    if label_name != settings.devin_trigger_label:
        return {"status": "ignored", "label": label_name}

    issue = payload["issue"]
    repo = payload["repository"]["full_name"]
    issue_number = issue["number"]
    issue_title = issue["title"]
    issue_body = issue.get("body") or ""

    logger.info("Trigger received — repo=%s issue=#%d label=%s", repo, issue_number, label_name)

    prompt = _build_prompt(issue_number, issue_title, issue_body, repo)

    try:
        session = await devin_client.create_session(
            prompt=prompt,
            idempotency_key=f"{repo}:issue:{issue_number}",
        )
    except Exception as exc:
        logger.exception("Failed to create Devin session")
        raise HTTPException(status_code=502, detail=f"Devin API error: {exc}") from exc

    session_id = session["session_id"]
    devin_url = session.get("url", "")

    await insert_session(session_id, issue_number, issue_title, repo, devin_url)

    await github_client.post_comment(
        repo,
        issue_number,
        f"## Devin is on it 🤖\n\n"
        f"A Devin session has been started to address this issue.\n\n"
        f"**Session ID:** `{session_id}`\n"
        f"**Devin URL:** {devin_url}\n\n"
        f"I'll post an update here once a pull request is ready.",
    )

    logger.info("Session %s created for issue #%d", session_id, issue_number)
    return {"status": "started", "session_id": session_id, "devin_url": devin_url}


@app.get("/sessions")
async def list_sessions():
    sessions = await get_all_sessions()
    return {"sessions": sessions, "total": len(sessions)}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    sessions = await get_all_sessions()
    for s in sessions:
        if s["session_id"] == session_id:
            return s
    raise HTTPException(status_code=404, detail="Session not found")


@app.get("/metrics")
async def metrics():
    sessions = await get_all_sessions()
    by_status: dict[str, int] = {}
    for s in sessions:
        by_status[s["status"]] = by_status.get(s["status"], 0) + 1

    completed = by_status.get("completed", 0)
    failed = by_status.get("failed", 0)
    denominator = completed + failed
    success_rate = round(completed / denominator * 100, 1) if denominator else 0.0

    return {
        "total_sessions": len(sessions),
        "by_status": by_status,
        "active_sessions": by_status.get("running", 0) + by_status.get("pending", 0),
        "success_rate_percent": success_rate,
    }


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    sessions = await get_all_sessions()

    STATUS_COLOR = {
        "completed": "#22c55e",
        "running":   "#3b82f6",
        "pending":   "#f59e0b",
        "failed":    "#ef4444",
        "blocked":   "#f97316",
    }

    rows = ""
    for s in sessions:
        color = STATUS_COLOR.get(s["status"], "#6b7280")
        pr_cell = (
            f'<a href="{s["pr_url"]}" target="_blank">View PR</a>'
            if s.get("pr_url") else "—"
        )
        devin_cell = (
            f'<a href="{s["devin_url"]}" target="_blank">Open</a>'
            if s.get("devin_url") else "—"
        )
        title = s["issue_title"]
        title_display = title[:55] + "…" if len(title) > 55 else title
        rows += (
            f"<tr>"
            f"<td>#{s['issue_number']}</td>"
            f"<td>{title_display}</td>"
            f"<td>{s['repo']}</td>"
            f"<td><span style='color:{color};font-weight:600'>{s['status'].upper()}</span></td>"
            f"<td>{devin_cell}</td>"
            f"<td>{pr_cell}</td>"
            f"<td>{s['created_at'][:16]}</td>"
            f"</tr>"
        )

    empty_row = (
        "<tr><td colspan='7' style='text-align:center;color:#64748b;padding:40px 0'>"
        "No sessions yet — label a GitHub issue with <code>devin-fix</code> to trigger automation."
        "</td></tr>"
    )

    m = await metrics()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="refresh" content="30">
  <title>Devin Automation · Dashboard</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f172a; color: #e2e8f0; min-height: 100vh; }}
    header {{ background: #1e293b; border-bottom: 1px solid #334155;
              padding: 20px 32px; display: flex; align-items: center; gap: 16px; }}
    header h1 {{ font-size: 20px; color: #f8fafc; }}
    header p  {{ color: #94a3b8; font-size: 13px; margin-top: 2px; }}
    .badge {{ background: #334155; color: #94a3b8; font-size: 11px;
              padding: 2px 8px; border-radius: 12px; }}
    .metrics {{ display: flex; gap: 12px; padding: 24px 32px; flex-wrap: wrap; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 10px;
             padding: 20px 24px; flex: 1; min-width: 140px; }}
    .card-val  {{ font-size: 34px; font-weight: 700; color: #f1f5f9; }}
    .card-label {{ color: #94a3b8; font-size: 12px; margin-top: 4px; text-transform: uppercase;
                   letter-spacing: .04em; }}
    .section {{ padding: 0 32px 32px; }}
    .refresh-note {{ color: #475569; font-size: 12px; padding: 0 32px 12px; }}
    table {{ width: 100%; border-collapse: collapse; background: #1e293b;
             border: 1px solid #334155; border-radius: 10px; overflow: hidden; }}
    th {{ background: #0f172a; color: #64748b; padding: 10px 16px; text-align: left;
          font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }}
    td {{ padding: 11px 16px; border-top: 1px solid #1e293b; font-size: 13px; }}
    tr:hover td {{ background: #1a2740; }}
    a {{ color: #60a5fa; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    code {{ background: #334155; color: #94a3b8; padding: 1px 5px; border-radius: 4px;
            font-size: 12px; }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Devin Automation Dashboard</h1>
      <p>Apache Superset · Issue Remediation · auto-refreshes every 30 s</p>
    </div>
    <span class="badge">trigger label: <strong>{settings.devin_trigger_label}</strong></span>
  </header>

  <div class="metrics">
    <div class="card">
      <div class="card-val">{m['total_sessions']}</div>
      <div class="card-label">Total Sessions</div>
    </div>
    <div class="card">
      <div class="card-val" style="color:#3b82f6">{m['active_sessions']}</div>
      <div class="card-label">Active</div>
    </div>
    <div class="card">
      <div class="card-val" style="color:#22c55e">{m['by_status'].get('completed', 0)}</div>
      <div class="card-label">Completed</div>
    </div>
    <div class="card">
      <div class="card-val" style="color:#ef4444">{m['by_status'].get('failed', 0)}</div>
      <div class="card-label">Failed</div>
    </div>
    <div class="card">
      <div class="card-val">{m['success_rate_percent']}%</div>
      <div class="card-label">Success Rate</div>
    </div>
  </div>

  <p class="refresh-note">Last loaded: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>

  <div class="section">
    <table>
      <thead>
        <tr>
          <th>Issue</th><th>Title</th><th>Repository</th>
          <th>Status</th><th>Devin</th><th>Pull Request</th><th>Started (UTC)</th>
        </tr>
      </thead>
      <tbody>
        {rows if rows else empty_row}
      </tbody>
    </table>
  </div>
</body>
</html>"""
