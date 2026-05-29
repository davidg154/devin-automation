from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SessionRecord(BaseModel):
    session_id: str
    issue_number: int
    issue_title: str
    repo: str
    status: str  # pending | running | completed | failed | blocked
    devin_url: Optional[str] = None
    pr_url: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
