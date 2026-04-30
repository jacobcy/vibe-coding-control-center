"""Shared guard utilities for flow task-binding checks."""

from typing import Any

from vibe3.exceptions import UserError


class MissingTaskIssueError(UserError):
    """Raised when current flow has no bound task issue."""

    def __str__(self) -> str:
        return self.message


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
