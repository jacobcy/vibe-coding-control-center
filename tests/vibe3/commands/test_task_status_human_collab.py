"""Tests for special sections of the task status dashboard:
governed anomaly, server labels, remote tasks, and human collaboration flows."""

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


def _make_config_mock() -> MagicMock:
    config_mock = MagicMock()
    config_mock.pid_file = "/tmp/vibe3.pid"
    config_mock.repo = "openai/vibe-center"
    config_mock.port = 1234
    config_mock.supervisor_handoff = MagicMock(issue_label="supervisor")
    config_mock.manager_usernames = ["manager-bot"]
    return config_mock


@patch("vibe3.config.load_orchestra_config")
@patch(
    "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
)
@patch("vibe3.services.task.status.FlowService")
@patch("vibe3.services.task.status.StatusQueryService")
def test_task_status_shows_governed_anomaly_section(
    mock_status_service_cls: MagicMock,
    mock_flow_service_cls: MagicMock,
    mock_fetch_live_snapshot: MagicMock,
    mock_load_orchestra_config: MagicMock,
) -> None:
    """Issue with governed label but no state appears in Governed but Anomaly."""
    config_mock = _make_config_mock()
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
            "number": 904,
            "title": "Governed but state missing",
            "state": None,
            "assignee": "manager-bot",
            "flow": None,
            "queued": False,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": ["orchestra-governed", "priority/3", "roadmap/p2"],
            "dispatch_exclusion_codes": ["missing_state_label"],
            "dispatch_exclusion_messages": ["missing state/* label"],
            "remote": False,
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    assert "Missing State Label - Governed but Anomaly:" in output
    assert "# 904" in output
    assert "Governed but state missing" in output
    assert "orchestra-governed label present" in output
    # Must not appear in Waiting section
    assert "Waiting for Assignee Pool" in output
    governed_section = output[output.find("Governed but Anomaly:") :]
    assert "# 904" in governed_section


class TestResolveServerLabel:
    """Tests for _resolve_server_label covering all branches."""

    def _call(self, snapshot_found: bool, server_running: bool, pid_valid: bool) -> str:
        from vibe3.commands.status import _resolve_server_label

        config = MagicMock()
        config.pid_file = "/tmp/vibe3.pid"
        with patch("vibe3.commands.status.validate_pid_file") as mock_pid:
            mock_pid.return_value = (1234, pid_valid)
            return _resolve_server_label(config, snapshot_found, server_running)

    def test_snapshot_and_server_running(self) -> None:
        result = self._call(snapshot_found=True, server_running=True, pid_valid=True)
        assert result == "[green]running[/]"

    def test_snapshot_found_server_down_pid_valid(self) -> None:
        result = self._call(snapshot_found=True, server_running=False, pid_valid=True)
        assert result == "[green]running[/]"

    def test_no_snapshot_server_down_pid_valid(self) -> None:
        result = self._call(snapshot_found=False, server_running=False, pid_valid=True)
        assert result == "[green]running[/]"

    def test_no_snapshot_server_down_pid_invalid(self) -> None:
        result = self._call(snapshot_found=False, server_running=False, pid_valid=False)
        assert result == "[dim]stopped[/]"


class TestComputeEffectiveServerRunning:
    """Tests for _compute_effective_server_running."""

    def _call(self, snapshot_running: bool, pid_valid: bool) -> bool:
        from vibe3.commands.status import _compute_effective_server_running

        config = MagicMock()
        config.pid_file = "/tmp/vibe3.pid"
        with patch("vibe3.commands.status.validate_pid_file") as mock_pid:
            mock_pid.return_value = (1234, pid_valid)
            return _compute_effective_server_running(snapshot_running, config)

    def test_snapshot_running_true(self) -> None:
        assert self._call(snapshot_running=True, pid_valid=False) is True
        assert self._call(snapshot_running=True, pid_valid=True) is True

    def test_snapshot_false_pid_valid(self) -> None:
        assert self._call(snapshot_running=False, pid_valid=True) is True

    def test_snapshot_false_pid_invalid(self) -> None:
        assert self._call(snapshot_running=False, pid_valid=False) is False


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
def test_task_status_shows_remote_tasks_section(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """task status should show remote tasks in a separate section."""
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
            "number": 505,
            "title": "Remote task on another machine",
            "state": IssueState.CLAIMED,
            "assignee": "manager-bot",
            "flow": None,
            "queued": False,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": [],
            "remote": True,
        },
        {
            "number": 606,
            "title": "Local task",
            "state": IssueState.CLAIMED,
            "assignee": "manager-bot",
            "flow": _make_flow(606),
            "queued": False,
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
    assert "Remote Tasks (no local flow):" in output
    assert "# 505" in output
    assert "Remote task on another machine" in output
    assert "Assignee Intake:" in output
    assert "# 606" in output
    intake_section = output[
        output.index("Assignee Intake:") : output.index("Ready Queue:")
    ]
    assert "# 505" not in intake_section


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
def test_human_collab_section_appears_for_dev_issue_flow(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """dev/issue-N flows should appear in Human Collaboration Flows section."""
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

    dev_flow = SimpleNamespace(
        branch="dev/issue-2122",
        flow_status="active",
        task_issue_number=2122,
        plan_ref=None,
        report_ref=None,
        latest_verdict=None,
        pr_number=None,
        pr_ref=None,
    )

    status_service = MagicMock()
    status_service.fetch_worktree_map.return_value = {}
    status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 2122,
            "title": "Dev collaboration issue",
            "state": IssueState.IN_PROGRESS,
            "assignee": "human-dev",
            "flow": dev_flow,
            "queued": False,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": [],
            "remote": False,
        },
        {
            "number": 303,
            "title": "Auto task",
            "state": IssueState.READY,
            "assignee": "manager-bot",
            "flow": _make_flow(303),
            "queued": False,
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

    # Human Collaboration Flows section should appear
    assert "Human Collaboration Flows:" in output

    # dev/issue-* flow should be in Human Collaboration section
    assert "#2122" in output or "# 2122" in output
    assert "Dev collaboration issue" in output
    assert "dev/issue-2122" in output

    # Auto task should still be in Issue Progress (Ready Queue)
    assert "Ready Queue:" in output
    assert "#303" in output or "# 303" in output

    # dev/issue-* flow should NOT be in Issue Progress section
    issue_progress_section = output[
        output.index("Issue Progress:") : output.index("Human Collaboration Flows:")
    ]
    assert (
        "#2122" not in issue_progress_section and "# 2122" not in issue_progress_section
    )


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
def test_blocked_dev_issue_not_in_blocked_section(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """Blocked dev/issue-N flows appear in Human Collab but NOT in Blocked section."""
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

    blocked_dev_flow = SimpleNamespace(
        branch="dev/issue-2200",
        flow_status="active",
        task_issue_number=2200,
        plan_ref=None,
        report_ref=None,
        latest_verdict=None,
        pr_number=None,
        pr_ref=None,
    )

    status_service = MagicMock()
    status_service.fetch_worktree_map.return_value = {}
    status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 2200,
            "title": "Blocked dev collab issue",
            "state": IssueState.BLOCKED,
            "assignee": "human-dev",
            "flow": blocked_dev_flow,
            "queued": False,
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

    assert "Human Collaboration Flows:" in output
    assert "#2200" in output or "# 2200" in output
    assert "Blocked dev collab issue" in output

    # Must NOT appear in blocked section
    assert "Blocked / Dependency Chain:" not in output
