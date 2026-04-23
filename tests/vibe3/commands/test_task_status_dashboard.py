"""Tests for the task status dashboard segmentation."""

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


@patch("vibe3.commands.status.load_orchestra_config")
@patch("vibe3.commands.status.OrchestraStatusService.fetch_live_snapshot")
@patch("vibe3.commands.status.FlowService")
@patch("vibe3.commands.status.StatusQueryService")
def test_task_status_splits_assignee_ready_and_anomaly(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
) -> None:
    """task status should keep intake, ready queue, and ready anomalies separate."""
    mock_load_orchestra_config.return_value = SimpleNamespace(
        pid_file="/tmp/vibe3.pid",
        repo="openai/vibe-center",
        port=1234,
    )
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
            "title": "Assigned but not ready",
            "state": IssueState.CLAIMED,
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
        },
        {
            "number": 202,
            "title": "Ready and assigned",
            "state": IssueState.READY,
            "assignee": "manager-bot",
            "flow": _make_flow(202),
            "queued": False,
            "failed_reason": None,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": [],
        },
        {
            "number": 303,
            "title": "Ready without assignee",
            "state": IssueState.READY,
            "assignee": None,
            "flow": _make_flow(303),
            "queued": False,
            "failed_reason": None,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": [],
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    assert output.index("Assignee Intake:") < output.index("Ready Queue:")
    assert output.index("Ready Queue:") < output.index("Ready Exceptions:")
    assert "manager-bot" in output
    assert "Ready without assignee" in output
    assert "historical debt" in output
