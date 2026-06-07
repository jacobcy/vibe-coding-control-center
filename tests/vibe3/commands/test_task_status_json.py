"""Tests for task status --format json functionality."""

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.models.orchestration import IssueState
from vibe3.services.orchestra_status_service import OrchestraSnapshot

runner = CliRunner(env={"NO_COLOR": "1"})


def _make_config_mock() -> MagicMock:
    """Create a standard config mock for tests."""
    config_mock = MagicMock()
    config_mock.pid_file = "/tmp/vibe3.pid"
    config_mock.repo = "openai/vibe-center"
    config_mock.port = 1234
    config_mock.supervisor_handoff = MagicMock(issue_label="supervisor")
    config_mock.manager_usernames = ["manager-bot"]
    return config_mock


@patch(
    "vibe3.services.orchestra_helpers.get_manager_usernames",
    return_value=["manager-bot"],
)
@patch("vibe3.config.orchestra_settings.load_orchestra_config")
@patch(
    "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
)
@patch("vibe3.services.task.status.FlowService")
@patch("vibe3.services.task.status.StatusQueryService")
def test_task_status_json_format(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """Test task status with --format json works correctly."""
    mock_load_orchestra_config.return_value = _make_config_mock()
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
            "flow": None,
            "queued": False,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": [],
            "remote": False,
        }
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["task", "status", "--format", "json"])

    assert result.exit_code == 0
    # Verify valid JSON output
    output_data = json.loads(result.stdout)
    assert "orchestra" in output_data
    assert "flows" in output_data
    assert "orchestrated_issues" in output_data
