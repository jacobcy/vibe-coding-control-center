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
@patch("vibe3.services.task_status_service.FlowService")
@patch("vibe3.services.task_status_service.StatusQueryService")
def test_task_status_splits_assignee_ready_and_anomaly(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """task status should keep intake, ready queue, and ready anomalies separate."""
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
            "title": "Assigned but not ready",
            "state": IssueState.CLAIMED,
            "assignee": "manager-bot",
            "flow": _make_flow(101),
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
            "number": 202,
            "title": "Ready and assigned",
            "state": IssueState.READY,
            "assignee": "manager-bot",
            "flow": _make_flow(202),
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
            "title": "Ready with human assignee",
            "state": IssueState.READY,
            "assignee": "jacobcy",
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
    assert output.index("Assignee Intake:") < output.index("Ready Queue:")
    assert output.index("Ready Queue:") < output.index("Ready Exceptions:")
    assert "manager-bot" in output
    assert "Ready with human assignee" in output
    assert "non-manager assignee" in output
    # Verify task status does NOT show system status sections
    assert "Vibe3 Configuration" not in output
    assert "Orchestra Status" not in output


@patch(
    "vibe3.services.orchestra_helpers.get_manager_usernames",
    return_value=["manager-bot"],
)
@patch("vibe3.config.orchestra_settings.load_orchestra_config")
@patch(
    "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
)
@patch("vibe3.services.task_status_service.FlowService")
@patch("vibe3.services.task_status_service.StatusQueryService")
def test_task_status_shows_flows_with_prs(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """task status should show flows that have a PR reference."""
    mock_load_orchestra_config.return_value = _make_config_mock()
    mock_fetch_live_snapshot.return_value = OrchestraSnapshot(
        timestamp=1234567890.0,
        server_running=True,
        active_issues=tuple(),
        active_flows=0,
        active_worktrees=0,
    )

    flow_with_pr = _make_flow(404)
    flow_with_pr.pr_ref = "https://github.com/openai/vibe-center/pull/1"

    status_service = MagicMock()
    status_service.fetch_worktree_map.return_value = {}
    status_service.fetch_orchestrated_issues.return_value = [
        {
            "number": 404,
            "title": "Flow with PR",
            "state": IssueState.REVIEW,
            "assignee": "manager-bot",
            "flow": flow_with_pr,
            "queued": False,
            "labels": [],
            "remote": False,
        }
    ]
    mock_status_service_cls.return_value = status_service
    mock_flow_service_cls.return_value = MagicMock(list_flows=lambda status: [])

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    assert "Flows with PRs (Merge-Ready/Done):" in result.output
    assert "# 404" in result.output
    assert "PR: https://github.com/openai/vibe-center/pull/1" in result.output


@patch(
    "vibe3.services.orchestra_helpers.get_manager_usernames",
    return_value=["manager-bot"],
)
@patch("vibe3.config.orchestra_settings.load_orchestra_config")
@patch(
    "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
)
@patch("vibe3.services.task_status_service.FlowService")
@patch("vibe3.services.task_status_service.StatusQueryService")
def test_task_status_hides_missing_blocked_issue_number(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
    mock_get_manager_usernames,
) -> None:
    """task status should not render '#None' when failed gate has no issue number."""
    mock_load_orchestra_config.return_value = _make_config_mock()
    mock_fetch_live_snapshot.return_value = OrchestraSnapshot(
        timestamp=1234567890.0,
        server_running=True,
        active_issues=tuple(),
        active_flows=0,
        active_worktrees=0,
        dispatch_blocked=True,
        blocked_reason="state/blocked",
        blocked_issue_number=None,
        blocked_issue_reason="API/Exec error threshold: 3 recent errors",
    )

    mock_flow_service_cls.return_value = MagicMock(list_flows=lambda status: [])
    status_service = MagicMock()
    status_service.fetch_worktree_map.return_value = {}
    status_service.fetch_orchestrated_issues.return_value = []
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    # System status sections should not appear in task status
    assert "Dispatch: FROZEN" not in result.output
    assert "Orchestra Status" not in result.output
    assert "Vibe3 Configuration" not in result.output


@patch("vibe3.config.orchestra_settings.load_orchestra_config")
@patch(
    "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
)
@patch("vibe3.services.task_status_service.FlowService")
@patch("vibe3.services.task_status_service.StatusQueryService")
def test_task_status_shows_missing_state_label_section(
    mock_status_service_cls,
    mock_flow_service_cls,
    mock_fetch_live_snapshot,
    mock_load_orchestra_config,
) -> None:
    """task status should show issues without state/* in a dedicated section."""
    config_mock = _make_config_mock()
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
            "number": 901,
            "title": "Missing state label issue",
            "state": None,
            "assignee": "manager-bot",
            "flow": None,
            "queued": False,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": [],
            "dispatch_exclusion_codes": ["missing_state_label"],
            "dispatch_exclusion_messages": ["missing state/* label"],
            "remote": False,
        },
        {
            "number": 902,
            "title": "Roadmap epic without state",
            "state": None,
            "assignee": None,
            "flow": None,
            "queued": False,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": "epic",
            "priority": 0,
            "labels": ["roadmap/epic"],
            "dispatch_exclusion_codes": ["missing_state_label", "roadmap_epic"],
            "dispatch_exclusion_messages": ["missing state/* label", "roadmap epic"],
            "remote": False,
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    assert "Missing State Label - Waiting for Assignee Pool:" in output
    assert "# 901" in output
    assert "Missing state label issue" in output
    assert "Roadmap Epic:" in output
    assert "Roadmap epic without state" in output
    assert output.count("Roadmap epic without state") == 1


@patch("vibe3.config.orchestra_settings.load_orchestra_config")
@patch(
    "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
)
@patch("vibe3.services.task_status_service.FlowService")
@patch("vibe3.services.task_status_service.StatusQueryService")
def test_task_status_shows_active_exception_for_missing_assignee(
    mock_status_service_cls: MagicMock,
    mock_flow_service_cls: MagicMock,
    mock_fetch_live_snapshot: MagicMock,
    mock_load_orchestra_config: MagicMock,
) -> None:
    """Active-state issue with missing assignee appears in Active Exceptions."""
    config_mock = _make_config_mock()
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
            "number": 903,
            "title": "Active state but no assignee",
            "state": IssueState.IN_PROGRESS,
            "assignee": None,
            "flow": None,
            "queued": False,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": [],
            "dispatch_exclusion_codes": [],
            "dispatch_exclusion_messages": [],
            "remote": False,
        },
    ]
    mock_status_service_cls.return_value = status_service

    result = runner.invoke(app, ["task", "status"])

    assert result.exit_code == 0
    output = result.output
    assert "Active Exceptions:" in output
    assert "# 903" in output
    assert "Active state but no assignee" in output
    assert "missing assignee" in output


@patch("vibe3.config.orchestra_settings.load_orchestra_config")
@patch(
    "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
)
@patch("vibe3.services.task_status_service.FlowService")
@patch("vibe3.services.task_status_service.StatusQueryService")
def test_task_status_shows_governed_anomaly_section(
    mock_status_service_cls: MagicMock,
    mock_flow_service_cls: MagicMock,
    mock_fetch_live_snapshot: MagicMock,
    mock_load_orchestra_config: MagicMock,
) -> None:
    """Issue with governed label but no state appears in Governed but Anomaly."""
    config_mock = _make_config_mock()
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
        with patch("vibe3.commands.status._validate_pid_file") as mock_pid:
            mock_pid.return_value = (1234, pid_valid)
            return _resolve_server_label(config, snapshot_found, server_running)

    def test_snapshot_and_server_running(self) -> None:
        """Both snapshot and server running → green running."""
        result = self._call(snapshot_found=True, server_running=True, pid_valid=True)
        assert result == "[green]running[/]"

    def test_snapshot_found_server_down_pid_valid(self) -> None:
        """Snapshot found but server down, PID valid → green running."""
        result = self._call(snapshot_found=True, server_running=False, pid_valid=True)
        assert result == "[green]running[/]"

    def test_no_snapshot_server_down_pid_valid(self) -> None:
        """No snapshot, server down, PID valid → green running."""
        result = self._call(snapshot_found=False, server_running=False, pid_valid=True)
        assert result == "[green]running[/]"

    def test_no_snapshot_server_down_pid_invalid(self) -> None:
        """No snapshot, server down, PID invalid → dim stopped."""
        result = self._call(snapshot_found=False, server_running=False, pid_valid=False)
        assert result == "[dim]stopped[/]"


class TestComputeEffectiveServerRunning:
    """Tests for _compute_effective_server_running."""

    def _call(self, snapshot_running: bool, pid_valid: bool) -> bool:
        from vibe3.commands.status import _compute_effective_server_running

        config = MagicMock()
        config.pid_file = "/tmp/vibe3.pid"
        with patch("vibe3.commands.status._validate_pid_file") as mock_pid:
            mock_pid.return_value = (1234, pid_valid)
            return _compute_effective_server_running(snapshot_running, config)

    def test_snapshot_running_true(self) -> None:
        """Snapshot says running → effective True regardless of PID."""
        assert self._call(snapshot_running=True, pid_valid=False) is True
        assert self._call(snapshot_running=True, pid_valid=True) is True

    def test_snapshot_false_pid_valid(self) -> None:
        """Snapshot says down but PID valid → effective True (fallback)."""
        assert self._call(snapshot_running=False, pid_valid=True) is True

    def test_snapshot_false_pid_invalid(self) -> None:
        """Snapshot says down and PID invalid → effective False."""
        assert self._call(snapshot_running=False, pid_valid=False) is False


@patch(
    "vibe3.services.orchestra_helpers.get_manager_usernames",
    return_value=["manager-bot"],
)
@patch("vibe3.config.orchestra_settings.load_orchestra_config")
@patch(
    "vibe3.services.orchestra_status_service.OrchestraStatusService.fetch_live_snapshot"
)
@patch("vibe3.services.task_status_service.FlowService")
@patch("vibe3.services.task_status_service.StatusQueryService")
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
            "flow": None,  # No local flow
            "queued": False,
            "blocked_by": None,
            "blocked_reason": None,
            "milestone": None,
            "roadmap": None,
            "priority": 0,
            "labels": [],
            "remote": True,  # Marked as remote
        },
        {
            "number": 606,
            "title": "Local task",
            "state": IssueState.CLAIMED,
            "assignee": "manager-bot",
            "flow": _make_flow(606),  # Has local flow
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
    # Remote tasks section should appear
    assert "Remote Tasks (no local flow):" in output
    # Remote issue should be in remote section
    assert "# 505" in output
    assert "Remote task on another machine" in output
    # Local task should still be in Assignee Intake
    assert "Assignee Intake:" in output
    assert "# 606" in output
    # Remote task should NOT be in Assignee Intake
    # (it should only appear in Remote Tasks section)
    intake_section = output[
        output.index("Assignee Intake:") : output.index("Ready Queue:")
    ]
    assert "# 505" not in intake_section
