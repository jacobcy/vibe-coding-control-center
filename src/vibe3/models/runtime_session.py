"""Runtime session domain model."""

import datetime

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.datetime.now().isoformat()


class RuntimeSession(BaseModel):
    """Represents a live agent session bound to a target (issue/pr/governance)."""

    id: int | None = None
    role: str
    """One of: manager / planner / executor / reviewer / governance"""
    target_type: str
    """One of: issue / pr / governance"""
    target_id: str
    branch: str
    session_name: str
    backend_session_id: str | None = None
    tmux_session: str | None = None
    log_path: str | None = None
    status: str = "starting"
    """One of: starting / running / done / failed / aborted / orphaned"""
    started_at: str | None = None
    ended_at: str | None = None
    worktree_path: str | None = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
