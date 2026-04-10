"""Tests for supervisor/apply execution routing."""

from unittest.mock import MagicMock, patch

from vibe3.execution.contracts import ExecutionLaunchResult
from vibe3.models.orchestra_config import OrchestraConfig, SupervisorHandoffConfig
from vibe3.orchestra.supervisor_run_service import (
    SUPERVISOR_APPLY_TASK,
    run_supervisor_mode,
)


@patch("vibe3.orchestra.supervisor_run_service.ExecutionCoordinator")
@patch("vibe3.orchestra.supervisor_run_service.SQLiteClient")
@patch("vibe3.orchestra.supervisor_run_service.OrchestraStatusService")
@patch("vibe3.execution.flow_dispatch.FlowManager")
@patch("vibe3.orchestra.supervisor_run_service.GovernanceService")
@patch("vibe3.orchestra.supervisor_run_service.CodeagentBackend")
@patch("vibe3.orchestra.supervisor_run_service.resolve_supervisor_agent_options")
@patch("vibe3.orchestra.supervisor_run_service.OrchestraConfig")
def test_run_supervisor_mode_uses_supervisor_config_and_task(
    mock_config_cls,
    mock_resolve_supervisor,
    mock_backend_cls,
    mock_governance_service,
    mock_flow_manager,
    mock_status_service,
    mock_sqlite_cls,
    mock_coordinator_cls,
):
    config = OrchestraConfig(
        supervisor_handoff=SupervisorHandoffConfig(
            supervisor_file="supervisor/apply.md",
            prompt_template="orchestra.supervisor.apply",
            agent="explore",
        )
    )
    mock_config_cls.from_settings.return_value = config
    mock_resolve_supervisor.return_value = MagicMock(
        backend="opencode",
        model="opencode/minimax-m2.5-free",
    )
    mock_governance_service.return_value.render_current_plan.return_value = "plan text"

    mock_coordinator = MagicMock()
    mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
        launched=True,
        tmux_session="vibe3-supervisor-apply",
        log_path="/tmp/supervisor.log",
    )
    mock_coordinator_cls.return_value = mock_coordinator

    run_supervisor_mode(
        supervisor_file="supervisor/apply.md",
        issue_number=None,
        dry_run=False,
        async_mode=True,
    )

    mock_resolve_supervisor.assert_called_once()
    mock_coordinator.dispatch_execution.assert_called_once()
    request = mock_coordinator.dispatch_execution.call_args[0][0]
    assert request.refs["task"] == SUPERVISOR_APPLY_TASK
    rendered_config = mock_governance_service.call_args.kwargs["config"]
    assert rendered_config.governance.prompt_template == "orchestra.supervisor.apply"
