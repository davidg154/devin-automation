"""
Create the three demo GitHub issues in your Superset fork and add
the 'devin-fix' label so the automation can pick them up.

Usage:
    python scripts/create_issues.py
"""

from __future__ import annotations

import os
import sys
import time

import httpx

GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPO = os.environ["GITHUB_REPO"]  # e.g. "your-username/superset"
TRIGGER_LABEL = os.environ.get("DEVIN_TRIGGER_LABEL", "devin-fix")

BASE = "https://api.github.com"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

ISSUES = [
    {
        "title": "bug: ORDINAL_MAP in date_parser.py is incomplete — ordinals beyond 'first' silently default to 1",
        "body": """## Problem

`superset/utils/date_parser.py` defines `ORDINAL_MAP` at line 64:

```python
ORDINAL_MAP: dict[str, int] = {
    "first": 1,
    "1st": 1,
}
```

`handle_nth_of()` uses this map on line 279:

```python
n = ORDINAL_MAP.get(ordinal.lower(), int(ordinal) if ordinal.isdigit() else 1)
```

The fallback when the ordinal is not in the map is `1`, so date expressions like:
- `"second week of the year"` → treated as first week  ❌
- `"third day of the month"` → treated as first day  ❌
- `"last week of the quarter"` → treated as first week  ❌

## Expected Behaviour

Ordinal words should map to their correct numeric values.

## Fix Required

Extend `ORDINAL_MAP` to include at least the ordinals that Superset's time-range grammar can produce:

| Word | Abbreviation | Value |
|------|-------------|-------|
| first | 1st | 1 |
| second | 2nd | 2 |
| third | 3rd | 3 |
| fourth | 4th | 4 |
| fifth | 5th | 5 |
| last | — | -1 (handled separately) |

Add unit tests in `tests/unit_tests/utils/test_date_parser.py` to cover each ordinal.

## Acceptance Criteria
- `ORDINAL_MAP` covers all valid ordinals the grammar emits
- `handle_nth_of("second", "week", "this", "year", None)` returns the second week
- Unit tests pass
""",
    },
    {
        "title": "chore: Modernize deprecated typing imports in superset/utils/json.py",
        "body": """## Problem

`superset/utils/json.py` imports `Dict`, `Optional`, and `Union` from the `typing` module
(line 22), which have been superseded by built-in generics and union syntax since Python 3.10.
The rest of the codebase already uses modern syntax (`dict[K, V]`, `X | Y`, etc.).

```python
# current (line 22) — deprecated style
from typing import Any, Callable, Dict, Optional, Union
```

## Fix Required

1. Add `from __future__ import annotations` at the top of the file (enables PEP 563).
2. Remove `Dict`, `Optional`, `Union` from the `typing` import.
3. Update all annotations in the file:
   - `Dict[K, V]`     → `dict[K, V]`
   - `Optional[X]`    → `X | None`
   - `Union[X, Y]`    → `X | Y`

The current usage in `DashboardEncoder.default` (line 43):
```python
def default(self, o: Any) -> Union[dict[Any, Any], str]:
```
should become:
```python
def default(self, o: Any) -> dict[Any, Any] | str:
```

## Acceptance Criteria
- No `Dict`, `Optional`, or `Union` imported from `typing` in this file
- `from __future__ import annotations` present
- `mypy` and `pylint` pass (no new errors)
- No functional changes
""",
    },
    {
        "title": "chore: Upgrade pandas from 2.1.4 to 2.2.x",
        "body": """## Problem

`requirements/base.txt` pins `pandas==2.1.4`. The 2.2.x series has been stable since
early 2024 and includes:

- Copy-on-Write (CoW) behaviour improvements that will become the default in pandas 3.0
- Performance improvements for `DataFrame.groupby` and `DataFrame.merge`
- Bug fixes in datetime timezone handling
- Better compatibility with NumPy 2.x

Staying on 2.1.x means we miss these fixes and accumulate technical debt before
the eventual pandas 3.0 migration.

## Fix Required

1. Update `requirements/base.in` to allow `pandas>=2.2,<3`.
2. Re-pin: update `requirements/base.txt` to `pandas==2.2.3` (or the latest 2.2.x release).
3. Scan `superset/utils/pandas.py` and any other direct pandas usage for deprecated API calls
   flagged in the 2.2.x migration guide (e.g. `DataFrame.swaplevel`, `Index.is_monotonic`,
   `fillna` with `method=`).
4. Fix any deprecation warnings found.
5. Run `python -m pytest tests/unit_tests/ -x -q` and confirm all tests pass.

## Acceptance Criteria
- `pandas==2.2.x` in requirements files
- No pandas deprecation warnings in the test run
- All unit tests green
""",
    },
]


def ensure_label(label: str) -> None:
    url = f"{BASE}/repos/{GITHUB_REPO}/labels"
    r = httpx.get(url, headers=HEADERS)
    existing = {lbl["name"] for lbl in r.json()} if r.is_success else set()
    if label not in existing:
        httpx.post(url, json={"name": label, "color": "0075ca"}, headers=HEADERS)
        print(f"  Created label '{label}'")


def create_issue(title: str, body: str) -> dict:
    r = httpx.post(
        f"{BASE}/repos/{GITHUB_REPO}/issues",
        json={"title": title, "body": body},
        headers=HEADERS,
    )
    r.raise_for_status()
    return r.json()


def add_label(issue_number: int, label: str) -> None:
    httpx.post(
        f"{BASE}/repos/{GITHUB_REPO}/issues/{issue_number}/labels",
        json={"labels": [label]},
        headers=HEADERS,
    ).raise_for_status()


def main() -> None:
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("Set GITHUB_TOKEN and GITHUB_REPO environment variables.")
        sys.exit(1)

    print(f"Creating issues in {GITHUB_REPO} …\n")
    ensure_label(TRIGGER_LABEL)

    for issue_def in ISSUES:
        issue = create_issue(issue_def["title"], issue_def["body"])
        num = issue["number"]
        url = issue["html_url"]
        print(f"  #{num}  {issue_def['title'][:70]}")
        print(f"        {url}")

        # Small delay so webhooks don't all fire simultaneously
        time.sleep(2)

        add_label(num, TRIGGER_LABEL)
        print(f"        → labeled '{TRIGGER_LABEL}' (automation will trigger)\n")


if __name__ == "__main__":
    main()
