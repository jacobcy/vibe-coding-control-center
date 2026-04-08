"""Tests for supervisor/apply execution routing."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestra_config import OrchestraConfig, SupervisorHandoffConfig
from vibe3.orchestra.supervisor_run_service import (
    SUPERVISOR_APPLY_TASK,
    run_supervisor_mode,
)


@patch("vibe3.orchestra.supervisor_run_service.OrchestraStatusService")
@patch("vibe3.manager.flow_manager.FlowManager")
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
    backend = MagicMock()
    mock_backend_cls.return_value = backend
    backend.start_async.return_value = MagicMock(
        tmux_session="vibe3-supervisor-apply",
        log_path="/tmp/supervisor.log",
    )

    run_supervisor_mode(
        supervisor_file="supervisor/apply.md",
        issue_number=None,
        dry_run=False,
        async_mode=True,
    )

    mock_resolve_supervisor.assert_called_once()
    backend.start_async.assert_called_once()
    assert backend.start_async.call_args.kwargs["task"] == SUPERVISOR_APPLY_TASK
    rendered_config = mock_governance_service.call_args.kwargs["config"]
    assert rendered_config.governance.prompt_template == "orchestra.supervisor.apply"
