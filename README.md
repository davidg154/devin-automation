# Devin Superset Automation

Event-driven system that automatically remediates GitHub issues in an Apache Superset fork using the [Devin API](https://docs.devin.ai/api-reference/overview).

When a GitHub issue is labeled `devin-fix`, the automation:
1. Creates a Devin session with a detailed remediation prompt
2. Polls Devin until the session completes
3. Posts the resulting PR link as a comment on the issue
4. Updates the live observability dashboard

---

## Architecture

```
GitHub Issue labeled 'devin-fix'
          │
          ▼ (webhook POST)
  ┌───────────────────┐
  │  FastAPI Server   │──────────────────► Devin API (create session)
  └───────────────────┘                         │
          │                              polls every 30 s
          ▼                                     ▼
     SQLite DB ◄──────────── Background worker (updates status)
          │                                     │
          └──────── GitHub comment ◄────────────┘
                   (PR link or failure notice)
```

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- A Devin API key — [get one here](https://app.devin.ai/settings/api)
- A GitHub personal access token with `repo` and `issues` scopes
- A fork of [apache/superset](https://github.com/apache/superset) in your GitHub account

---

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/davidg154/devin-automation
cd devin-automation
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
DEVIN_API_KEY=your_devin_api_key
GITHUB_TOKEN=your_github_pat
GITHUB_REPO=your-username/superset
WEBHOOK_SECRET=any_random_string
```

### 2. Start the server

```bash
docker compose up --build -d
```

The server starts on `http://localhost:8000`. Verify it's running:

```bash
curl http://localhost:8000/health
# → {"status":"ok","timestamp":"..."}
```

### 3. Create the demo issues

This creates three pre-built issues in your Superset fork (bug fix, code quality, dependency upgrade):

```bash
docker compose exec automation python scripts/create_issues.py
```

---

## Simulating the Workflow (no webhook setup required)

The easiest way to trigger the automation is the simulate script — no public URL or ngrok needed.

```bash
# Trigger all 3 issues at once
docker compose exec automation python scripts/simulate_webhook.py

# Trigger a single issue by number
docker compose exec automation python scripts/simulate_webhook.py 2
```

This fires a signed `issues.labeled` webhook payload directly at the local server, which creates a Devin session for each issue. Watch progress on the dashboard:

```
http://localhost:8000/dashboard
```

---

## Setting Up a Real GitHub Webhook (optional)

To trigger automatically when anyone labels a real issue:

1. Expose your server with [ngrok](https://ngrok.com):
   ```bash
   ngrok http 8000
   # → Forwarding: https://abc123.ngrok-free.app
   ```

2. In your Superset fork → **Settings → Webhooks → Add webhook**:

   | Field | Value |
   |-------|-------|
   | Payload URL | `https://abc123.ngrok-free.app/webhook` |
   | Content type | `application/json` |
   | Secret | value of `WEBHOOK_SECRET` from `.env` |
   | Events | **Issues** only |

3. Label any issue with `devin-fix` — the automation triggers automatically.

---

## Observability

| URL | Description |
|-----|-------------|
| `http://localhost:8000/dashboard` | Live HTML dashboard (auto-refreshes every 30 s) |
| `http://localhost:8000/metrics` | JSON metrics — total, active, success rate |
| `http://localhost:8000/sessions` | JSON list of all sessions |
| `http://localhost:8000/sessions/{id}` | JSON detail for one session |
| `http://localhost:8000/health` | Health check |

The dashboard shows each session's status (`RUNNING`, `COMPLETED`, `FAILED`, `BLOCKED`), a link to the Devin session, and the resulting pull request once Devin finishes.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DEVIN_API_KEY` | Yes | — | Devin API key |
| `GITHUB_TOKEN` | Yes | — | GitHub PAT (`repo` + `issues` scopes) |
| `GITHUB_REPO` | Yes | — | `owner/repo` of your Superset fork |
| `WEBHOOK_SECRET` | Recommended | — | HMAC secret for webhook signature verification |
| `DEVIN_TRIGGER_LABEL` | No | `devin-fix` | Label that triggers the automation |
| `POLL_INTERVAL_SECONDS` | No | `30` | How often to poll Devin for status updates |
| `DATABASE_PATH` | No | `data/sessions.db` | SQLite file path inside the container |

---

## Demo Issues

The `create_issues.py` script creates these three issues:

| # | Type | Description |
|---|------|-------------|
| 1 | Bug | `ORDINAL_MAP` in `date_parser.py` is incomplete — ordinals beyond "first" silently default to 1 |
| 2 | Code quality | Deprecated `typing.Dict/Optional/Union` imports in `json.py` need modernizing |
| 3 | Dependency | Upgrade `pandas` from `2.1.4` to `2.2.x` |

---

## Stopping the Server

```bash
docker compose down
```

Logs are available with:

```bash
docker compose logs -f
```
