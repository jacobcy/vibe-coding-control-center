"""Tests for RFC/Epic label handling in task status dashboard."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.orchestration import IssueState
from vibe3.services import OrchestraSnapshot

runner = CliRunner(env={"NO_COLOR": "1"})


def _make_flow(issue_number: int) -> SimpleNamespace:
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


@patch("vibe3.commands.status.load_orchestra_config")
@patch("vibe3.commands.status.OrchestraStatusService.fetch_live_snapshot")
@patch("vibe3.commands.status.FlowService")
@patch("vibe3.commands.status.StatusQueryService")
def test_task_status_shows_rfc_and_epic_in_separate_sections(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
) -> None:
    """task status should show RFC and Epic issues in their own sections."""
    config_mock = MagicMock()
    config_mock.pid_file = "/tmp/vibe3.pid"
    config_mock.repo = "openai/vibe-center"
    config_mock.port = 1234
    config_mock.supervisor_handoff = MagicMock(issue_label="supervisor")
    config_mock.manager_usernames = ["manager-bot"]
    config_mock.get_manager_usernames.return_value = ["manager-bot"]
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
            "number": 777,
            "title": "RFC design needed",
            "state": IssueState.BLOCKED,
            "assignee": "manager-bot",
            "flow": _make_flow(777),
            "queued": False,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": ["roadmap/rfc"],
            "remote": False,
        },
        {
            "number": 888,
            "title": "Epic container issue",
            "state": IssueState.BLOCKED,
            "assignee": "manager-bot",
            "flow": _make_flow(888),
            "queued": False,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": ["roadmap/epic"],
            "remote": False,
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    # RFC section should appear
    assert "Roadmap RFC:" in output
    assert "# 777" in output
    assert "RFC design needed" in output
    # Epic section should appear
    assert "Roadmap Epic:" in output
    assert "# 888" in output
    assert "Epic container issue" in output


@patch("vibe3.commands.status.load_orchestra_config")
@patch("vibe3.commands.status.OrchestraStatusService.fetch_live_snapshot")
@patch("vibe3.commands.status.FlowService")
@patch("vibe3.commands.status.StatusQueryService")
def test_task_status_blocked_issues_excludes_rfc_and_epic(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
) -> None:
    """Blocked Issues section should exclude RFC/Epic labeled items."""
    config_mock = MagicMock()
    config_mock.pid_file = "/tmp/vibe3.pid"
    config_mock.repo = "openai/vibe-center"
    config_mock.port = 1234
    config_mock.supervisor_handoff = MagicMock(issue_label="supervisor")
    config_mock.manager_usernames = ["manager-bot"]
    config_mock.get_manager_usernames.return_value = ["manager-bot"]
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
            "number": 999,
            "title": "Regular blocked issue",
            "state": IssueState.BLOCKED,
            "assignee": "manager-bot",
            "flow": _make_flow(999),
            "queued": False,
            "blocked_by": None,
            "blocked_reason": "dependency missing",
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": [],  # No RFC/Epic labels
            "remote": False,
        },
        {
            "number": 777,
            "title": "RFC blocked issue",
            "state": IssueState.BLOCKED,
            "assignee": "manager-bot",
            "flow": _make_flow(777),
            "queued": False,
            "blocked_by": None,
            "blocked_reason": "needs design input",
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": ["roadmap/rfc"],
            "remote": False,
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    # Regular blocked issue should be in Blocked Issues section
    assert "Blocked Issues:" in output
    blocked_section_start = output.index("Blocked Issues:")
    blocked_section_end = output.find("\n\n", blocked_section_start)
    if blocked_section_end == -1:
        blocked_section_end = len(output)
    blocked_section = output[blocked_section_start:blocked_section_end]
    assert "# 999" in blocked_section
    assert "Regular blocked issue" in blocked_section
    # RFC issue should NOT be in Blocked Issues section
    assert "# 777" not in blocked_section
    # RFC issue should be in Roadmap RFC section
    assert "Roadmap RFC:" in output
    rfc_section_start = output.index("Roadmap RFC:")
    rfc_section_end = output.find("\n\n", rfc_section_start)
    if rfc_section_end == -1:
        rfc_section_end = len(output)
    rfc_section = output[rfc_section_start:rfc_section_end]
    assert "# 777" in rfc_section
