"""Test utilities for RFC/Epic tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from vibe3.models.orchestration import IssueState
from vibe3.services.orchestra.status import OrchestraSnapshot


def make_flow(issue_number: int) -> SimpleNamespace:
    """Create a mock flow object."""
    return SimpleNamespace(
        branch=f"task/issue-{issue_number}",
        flow_status="active",
        task_issue_number=issue_number,
        plan_ref=None,
        report_ref=None,
        latest_verdict=None,
        pr_number=None,
        pr_ref=None,
    )


def make_issue(
    number: int,
    title: str,
    state: IssueState = IssueState.BLOCKED,
    labels: list[str] | None = None,
    body: str | None = None,
    blocked_reason: str | None = None,
    blocked_by: tuple[int, ...] | None = None,
    assignee: str = "manager-bot",
) -> dict:
    """Create a mock issue dict."""
    return {
        "number": number,
        "title": title,
        "state": state,
        "assignee": assignee,
        "flow": make_flow(number),
        "queued": False,
        "blocked_by": blocked_by,
        "blocked_reason": blocked_reason,
        "milestone": None,
        "roadmap": None,
        "priority": 0,
        "labels": labels or [],
        "remote": False,
        "body": body,
    }


def make_orchestra_config():
    """Create a mock orchestra config for RFC/Epic tests."""
    config_mock = MagicMock()
    config_mock.pid_file = "/tmp/vibe3.pid"
    config_mock.repo = "openai/vibe-center"
    config_mock.port = 1234
    config_mock.supervisor_handoff = MagicMock(issue_label="supervisor")
    config_mock.manager_usernames = ["manager-bot"]
    config_mock.get_manager_usernames.return_value = ["manager-bot"]
    return config_mock


def make_orchestra_snapshot():
    """Create a mock orchestra snapshot for RFC/Epic tests."""
    return OrchestraSnapshot(
        timestamp=1234567890.0,
        server_running=True,
        active_issues=tuple(),
        active_flows=0,
        active_worktrees=0,
    )
