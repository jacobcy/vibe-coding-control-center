"""Shared guard and helper utilities for flow execution.

This module combines:
- Task binding guards (MissingTaskIssueError, ensure_task_issue_bound)
- Role block function helpers (get_role_block_function)
- Issue failure event emission (emit_issue_failed)
"""

from __future__ import annotations

from typing import Any, Callable

from vibe3.exceptions import UserError
from vibe3.models import IssueFailed, publish

# -- Task binding guards ------------------------------------------------


class MissingTaskIssueError(UserError):
    """Raised when current flow has no bound task issue."""


def has_task_issue(flow_status: Any | None) -> bool:
    """Return True when flow status includes a task_issue_number."""
    if flow_status is None:
        return False
    return getattr(flow_status, "task_issue_number", None) is not None


def build_bind_task_hint() -> str:
    """Return the canonical task bind hint."""
    return "先执行 `vibe3 flow bind <issue> --role task`"


def build_missing_task_issue_message(force_command: str) -> str:
    """Return canonical error message for missing task issue guard."""
    return (
        "Error: 当前 flow 未绑定 task issue\n"
        f"{build_bind_task_hint()}\n"
        f"若确认强制继续，使用 `{force_command}`"
    )


def ensure_task_issue_bound(
    flow_status: Any | None,
    *,
    yes: bool,
    force_command: str,
) -> None:
    """Validate task binding unless caller explicitly bypasses with --yes."""
    if yes or has_task_issue(flow_status):
        return
    raise MissingTaskIssueError(build_missing_task_issue_message(force_command))


# -- Role block functions -----------------------------------------------


def get_role_block_function(role: str) -> Callable[..., None]:
    """Get the block function for a given role."""
    import importlib

    _failure = importlib.import_module("vibe3.services.issue.failure")
    block_fns: dict[str, Callable[..., None]] = {
        "manager": _failure.block_manager_noop_issue,
        "planner": _failure.block_planner_noop_issue,
        "executor": _failure.block_executor_noop_issue,
        "reviewer": _failure.block_reviewer_noop_issue,
    }
    return block_fns[role]


# -- Event emission helpers --------------------------------------------


def emit_issue_failed(
    issue_number: int,
    reason: str,
    actor: str = "system",
    role: str | None = None,
) -> None:
    """Publish an IssueFailed domain event."""
    publish(
        IssueFailed(issue_number=issue_number, reason=reason, actor=actor, role=role)
    )
