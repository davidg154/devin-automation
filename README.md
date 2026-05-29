# Devin Superset Automation

Event-driven system that automatically remediates GitHub issues in an Apache Superset fork using the [Devin API](https://docs.devin.ai/api-reference/overview).

## Architecture

```
GitHub Issue labeled 'devin-fix'
          │
          ▼ (webhook)
  ┌───────────────────┐
  │  FastAPI Server   │  POST /webhook
  │  (this service)   │──────────────────► Devin API (create session)
  └───────────────────┘                         │
          │                                     │ (async, polls every 30 s)
          ▼                                     ▼
     SQLite DB          ◄──── Background worker (polls session status)
          │                                     │
          └──────── GitHub comment ◄────────────┘
                   (PR link or failure notice)
```

**Trigger:** GitHub `issues.labeled` webhook fires when the `devin-fix` label is added to an issue.

**Processing:** The server creates a Devin session with a detailed prompt describing the repo, issue, and instructions. A background worker polls Devin every 30 seconds.

**Output:** When the session finishes, the worker posts a GitHub comment with the PR link and updates the SQLite database.

**Observability:** `/dashboard` provides a live HTML view of all sessions, their status, and a success-rate metric.

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/your-username/devin-automation
cd devin-automation
cp .env.example .env
# Edit .env with your keys
```

### 2. Build and run

```bash
docker compose up --build
```

The server starts on `http://localhost:8000`.

### 3. Expose the webhook endpoint

GitHub needs to reach your server. Use [ngrok](https://ngrok.com) or a similar tunnel:

```bash
ngrok http 8000
```

Copy the HTTPS URL (e.g. `https://abc123.ngrok-free.app`).

### 4. Register the GitHub webhook

In your Superset fork → **Settings → Webhooks → Add webhook**:

| Field | Value |
|-------|-------|
| Payload URL | `https://abc123.ngrok-free.app/webhook` |
| Content type | `application/json` |
| Secret | value of `WEBHOOK_SECRET` in `.env` |
| Events | `Issues` only |

### 5. Create issues (manual or automated)

**Option A — automated script** (creates all three demo issues and labels them):

```bash
# From inside the container or with dependencies installed locally
GITHUB_TOKEN=... GITHUB_REPO=your-username/superset \
  python scripts/create_issues.py
```

**Option B — manually** in your fork's Issues tab. Add the `devin-fix` label to trigger the automation.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/webhook` | GitHub webhook receiver |
| `GET` | `/dashboard` | Live HTML observability dashboard |
| `GET` | `/sessions` | JSON list of all sessions |
| `GET` | `/sessions/{id}` | JSON detail for one session |
| `GET` | `/metrics` | Aggregate success/failure counts |
| `GET` | `/health` | Health check |

---

## Demo Issues (pre-built)

The `create_issues.py` script creates these three issues in your fork:

| # | Type | File | Description |
|---|------|------|-------------|
| 1 | Bug | `superset/utils/date_parser.py` | `ORDINAL_MAP` incomplete — ordinals beyond "first" silently default to 1 |
| 2 | Code quality | `superset/utils/json.py` | Deprecated `typing.Dict/Optional/Union` imports need modernizing |
| 3 | Dependency | `requirements/base.txt` | Upgrade `pandas` from `2.1.4` to `2.2.x` |

---

## Observability

Open `http://localhost:8000/dashboard` to see:

- **Active sessions** — sessions currently running in Devin
- **Completed** — sessions that produced a PR
- **Failed** — sessions that finished without a PR
- **Success rate** — `completed / (completed + failed)`
- Per-session links to the Devin session URL and the resulting PR

The page auto-refreshes every 30 seconds. For production use, add a time-series database (e.g. Prometheus + Grafana) by scraping `/metrics`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DEVIN_API_KEY` | Yes | Devin API key |
| `GITHUB_TOKEN` | Yes | GitHub PAT with `repo` + `issues` scopes |
| `GITHUB_REPO` | Yes | `owner/repo` of your Superset fork |
| `WEBHOOK_SECRET` | Recommended | HMAC secret for webhook signature verification |
| `DEVIN_TRIGGER_LABEL` | No | Label to watch for (default: `devin-fix`) |
| `POLL_INTERVAL_SECONDS` | No | Status poll frequency (default: `30`) |
| `DATABASE_PATH` | No | SQLite file path (default: `data/sessions.db`) |
