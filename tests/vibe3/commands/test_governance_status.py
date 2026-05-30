"""Tests for the governance status command."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.orchestration import IssueState
from vibe3.services.orchestra_status_service import OrchestraSnapshot

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


@patch("vibe3.commands.status.get_manager_usernames", return_value=["manager-bot"])
@patch("vibe3.commands.status.load_orchestra_config")
@patch("vibe3.commands.status.OrchestraStatusService.fetch_live_snapshot")
@patch("vibe3.commands.status.FlowService")
@patch("vibe3.commands.status.StatusQueryService")
def test_governance_status_table_output(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """Governance status should render all sections in table format."""
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
    status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 101,
            "title": "Manager assigned task",
            "state": IssueState.CLAIMED,
            "assignee": "manager-bot",
            "flow": _make_flow(101),
            "queued": False,
            "labels": [],
            "remote": False,
        },
        {
            "number": 102,
            "title": "RFC: Design proposal",
            "state": IssueState.READY,
            "assignee": "manager-bot",
            "flow": _make_flow(102),
            "queued": False,
            "labels": ["roadmap/rfc"],
            "remote": False,
        },
        {
            "number": 103,
            "title": "Epic: Q1 roadmap",
            "state": IssueState.CLAIMED,
            "assignee": "manager-bot",
            "flow": _make_flow(103),
            "queued": False,
            "labels": ["roadmap/epic"],
            "remote": False,
        },
        {
            "number": 104,
            "title": "Blocked task",
            "state": IssueState.BLOCKED,
            "assignee": "manager-bot",
            "flow": _make_flow(104),
            "queued": False,
            "labels": [],
            "remote": False,
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    output = result.output
    # Check all sections are present
    assert "Governance Status" in output
    assert "Manager-Assigned Issues: 4" in output
    assert "RFC Issues: 1" in output
    assert "Epic Issues: 1" in output
    assert "Blocked Issues: 1" in output
    assert "Pool Health" in output
    # Check specific items
    assert "Manager assigned task" in output
    assert "RFC: Design proposal" in output
    assert "Epic: Q1 roadmap" in output
    assert "Blocked task" in output


@patch("vibe3.commands.status.get_manager_usernames", return_value=["manager-bot"])
@patch("vibe3.commands.status.load_orchestra_config")
@patch("vibe3.commands.status.OrchestraStatusService.fetch_live_snapshot")
@patch("vibe3.commands.status.FlowService")
@patch("vibe3.commands.status.StatusQueryService")
def test_governance_status_json_output(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """Governance status should output JSON with expected keys."""
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
    status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 101,
            "title": "Manager assigned task",
            "state": IssueState.CLAIMED,
            "assignee": "manager-bot",
            "flow": _make_flow(101),
            "queued": False,
            "labels": [],
            "remote": False,
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["status", "--json"])

    assert result.exit_code == 0
    # Parse JSON output
    output_data = json.loads(result.output)
    # Check expected keys exist
    assert "manager_assigned" in output_data
    assert "rfc_items" in output_data
    assert "epic_items" in output_data
    assert "blocked_items" in output_data
    assert "pool_health" in output_data
    # Check pool_health sub-keys
    assert "manager_assigned_total" in output_data["pool_health"]
    assert "waiting_for_governance" in output_data["pool_health"]
    assert "state_missing_governed_anomaly" in output_data["pool_health"]
    # Check data content
    assert len(output_data["manager_assigned"]) == 1
    assert output_data["pool_health"]["manager_assigned_total"] == 1


@patch("vibe3.commands.status.get_manager_usernames", return_value=["manager-bot"])
@patch("vibe3.commands.status.load_orchestra_config")
@patch("vibe3.commands.status.OrchestraStatusService.fetch_live_snapshot")
@patch("vibe3.commands.status.FlowService")
@patch("vibe3.commands.status.StatusQueryService")
def test_governance_status_empty_repo(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """Governance status should render gracefully with no issues."""
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
    status_service.fetch_orchestrated_issues.return_value = []
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    output = result.output
    # All sections should show "(none)"
    assert "Manager-Assigned Issues: 0" in output
    assert "RFC Issues: 0" in output
    assert "Epic Issues: 0" in output
    assert "Blocked Issues: 0" in output
    # Should show zero counts in pool health
    assert "Manager-assigned (total): 0" in output
    assert "Waiting for governance: 0" in output
    assert "State-missing (governed anomaly): 0" in output


@patch("vibe3.commands.status.get_manager_usernames", return_value=["manager-bot"])
@patch("vibe3.commands.status.load_orchestra_config")
@patch("vibe3.commands.status.OrchestraStatusService.fetch_live_snapshot")
@patch("vibe3.commands.status.FlowService")
@patch("vibe3.commands.status.StatusQueryService")
def test_governance_status_manager_assigned_filtering(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """Governance status should only count manager-assigned issues."""
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
    status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 101,
            "title": "Manager assigned",
            "state": IssueState.CLAIMED,
            "assignee": "manager-bot",
            "flow": _make_flow(101),
            "queued": False,
            "labels": [],
            "remote": False,
        },
        {
            "number": 102,
            "title": "Human assigned",
            "state": IssueState.CLAIMED,
            "assignee": "jacobcy",
            "flow": _make_flow(102),
            "queued": False,
            "labels": [],
            "remote": False,
        },
        {
            "number": 103,
            "title": "Unassigned",
            "state": IssueState.READY,
            "assignee": None,
            "flow": _make_flow(103),
            "queued": False,
            "labels": [],
            "remote": False,
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    output = result.output
    # Should only count manager-assigned issue
    assert "Manager-Assigned Issues: 1" in output
    assert "Manager assigned" in output
    # Human-assigned and unassigned should not appear in manager-assigned section
    assert "Human assigned" not in output
    assert "Unassigned" not in output


@patch("vibe3.commands.status.get_manager_usernames", return_value=["manager-bot"])
@patch("vibe3.commands.status.load_orchestra_config")
@patch("vibe3.commands.status.OrchestraStatusService.fetch_live_snapshot")
@patch("vibe3.commands.status.FlowService")
@patch("vibe3.commands.status.StatusQueryService")
def test_governance_status_waiting_pool_and_anomaly(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """Governance status should separate waiting pool from governed anomaly."""
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
    status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 101,
            "title": "Waiting for governance",
            "state": None,
            "assignee": "manager-bot",
            "flow": _make_flow(101),
            "queued": False,
            "labels": [],
            "remote": False,
        },
        {
            "number": 102,
            "title": "Governed but missing state",
            "state": None,
            "assignee": "manager-bot",
            "flow": _make_flow(102),
            "queued": False,
            "labels": ["orchestra-governed"],
            "remote": False,
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    output = result.output
    # Check pool health shows both categories
    assert "Waiting for governance: 1" in output
    assert "#101" in output
    assert "State-missing (governed anomaly): 1" in output
    assert "#102" in output
