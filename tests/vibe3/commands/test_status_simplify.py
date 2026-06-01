"""Tests for status simplification (issue #1782).

These tests verify that vibe3 status shows basic config only,
while vibe3 task status shows full task progress dashboard.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.orchestration import IssueState
from vibe3.services.orchestra_status_service import OrchestraSnapshot

runner = CliRunner(env={"NO_COLOR": "1"})


def _make_flow(issue_number: int) -> SimpleNamespace:
    """Create a minimal flow object for testing."""
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


@patch(
    "vibe3.services.orchestra_helpers.get_manager_usernames",
    return_value=["manager-bot"],
)
@patch("vibe3.commands.status.load_orchestra_config")
@patch(
    "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
)
def test_status_without_task_progress_shows_basic_config_only(
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """vibe3 status (top-level) should only show basic config, not task progress."""
    config_mock = MagicMock()
    config_mock.pid_file = "/tmp/vibe3.pid"
    config_mock.repo = "openai/vibe-center"
    config_mock.port = 1234
    config_mock.supervisor_handoff = MagicMock(issue_label="supervisor")
    config_mock.manager_usernames = ["manager-bot"]
    config_mock.max_concurrent_flows = 3
    config_mock.polling_interval = 30
    config_mock.scene_base_ref = "main"
    mock_load_orchestra_config.return_value = config_mock
    mock_fetch_live_snapshot.return_value = OrchestraSnapshot(
        timestamp=1234567890.0,
        server_running=True,
        active_issues=tuple(),
        active_flows=0,
        active_worktrees=0,
    )

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    output = result.output
    # Should show Orchestra Status and Vibe3 Configuration
    assert "Orchestra Status" in output
    assert "Vibe3 Configuration" in output
    # Should NOT show Issue Progress sections
    assert "Issue Progress" not in output
    assert "Assignee Intake:" not in output
    assert "Ready Queue:" not in output
    # Should show the hint message
    assert "Use `vibe3 task status` to view issue progress and ready queue" in output


@patch(
    "vibe3.services.orchestra_helpers.get_manager_usernames",
    return_value=["manager-bot"],
)
@patch("vibe3.commands.status.load_orchestra_config")
@patch(
    "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
)
@patch("vibe3.commands.status.FlowService")
@patch("vibe3.services.status_query_service.StatusQueryService")
def test_task_status_shows_full_task_progress(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """vibe3 task status should still show full task progress."""
    config_mock = MagicMock()
    config_mock.pid_file = "/tmp/vibe3.pid"
    config_mock.repo = "openai/vibe-center"
    config_mock.port = 1234
    config_mock.supervisor_handoff = MagicMock(issue_label="supervisor")
    config_mock.manager_usernames = ["manager-bot"]
    mock_load_orchestra_config.return_value = config_mock
    mock_fetch_live_snapshot.return_value = OrchestraSnapshot(
        timestamp=1234567890.0,
        server_running=True,
        active_issues=tuple(),
        active_flows=0,
        active_worktrees=0,
    )

    flow_service = MagicMock()
    flow_service.list_flows.return_value = []
    mock_flow_service_cls.return_value = flow_service

    status_service = MagicMock()
    status_service.fetch_worktree_map.return_value = {}
    status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 101,
            "title": "Test issue",
            "state": IssueState.READY,
            "assignee": "manager-bot",
            "flow": _make_flow(101),
            "queued": False,
            "failed_reason": None,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": [],
            "remote": False,
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    # Should show Orchestra Status and Vibe3 Configuration
    assert "Orchestra Status" in output
    assert "Vibe3 Configuration" in output
    # Should show Issue Progress sections
    assert "Issue Progress" in output
    assert "Ready Queue:" in output
    assert "# 101" in output
    # Should NOT show the hint message
    assert "Use `vibe3 task status` to view issue progress" not in output
