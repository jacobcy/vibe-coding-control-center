"""Tests for governance scan domain event handler."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.governance import GovernanceScanStarted
from vibe3.execution.contracts import ExecutionLaunchResult


class TestGovernanceScanHandler:
    """governance_scan handler dispatches governance agent via coordinator."""

    @patch("vibe3.orchestra.logging.append_governance_event")
    @patch("vibe3.environment.session_registry.SessionRegistryService")
    @patch("vibe3.agents.backends.codeagent.CodeagentBackend")
    @patch("vibe3.clients.sqlite_client.SQLiteClient")
    @patch("vibe3.services.orchestra_status_service.OrchestraStatusService")
    @patch("vibe3.execution.flow_dispatch.FlowManager")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.models.orchestra_config.OrchestraConfig.from_settings")
    @patch("vibe3.roles.governance.build_governance_request")
    def test_skips_when_governance_already_running(
        self,
        mock_build_request: MagicMock,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_flow_cls: MagicMock,
        mock_status_cls: MagicMock,
        mock_sqlite_cls: MagicMock,
        mock_backend_cls: MagicMock,
        mock_registry_cls: MagicMock,
        mock_append_governance_event: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.governance_scan import (
            handle_governance_scan_started,
        )

        mock_config = MagicMock(dry_run=False, governance_max_concurrent=1)
        mock_from_settings.return_value = mock_config

        mock_registry = MagicMock()
        mock_registry.list_live_governance_sessions.return_value = [
            {"tmux_session": "vibe3-governance-scan-20260421-045821-t1"}
        ]
        mock_registry_cls.return_value = mock_registry

        handle_governance_scan_started(GovernanceScanStarted(tick_count=5))

        mock_registry.mark_governance_sessions_done_when_tmux_gone.assert_called_once()
        mock_build_request.assert_not_called()
        mock_coordinator_cls.return_value.dispatch_execution.assert_not_called()
        mock_append_governance_event.assert_called_once()
        assert (
            "governance already running"
            in mock_append_governance_event.call_args.args[0]
        )

    @patch("vibe3.services.orchestra_status_service.OrchestraStatusService")
    @patch("vibe3.execution.flow_dispatch.FlowManager")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.models.orchestra_config.OrchestraConfig.from_settings")
    @patch("vibe3.roles.governance.build_governance_request")
    def test_normal_dispatch(
        self,
        mock_build_request: MagicMock,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_flow_cls: MagicMock,
        mock_status_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.governance_scan import (
            handle_governance_scan_started,
        )

        mock_config = MagicMock(dry_run=False, governance_max_concurrent=1)
        mock_from_settings.return_value = mock_config

        mock_request = MagicMock()
        mock_build_request.return_value = mock_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True, tmux_session="vibe3-gov-1", log_path="/tmp/gov.log"
        )
        mock_coordinator_cls.return_value = mock_coordinator

        mock_status = MagicMock()
        mock_snapshot = MagicMock()
        mock_snapshot.circuit_breaker_state = "closed"
        mock_status.snapshot.return_value = mock_snapshot
        mock_status_cls.return_value = mock_status

        handle_governance_scan_started(GovernanceScanStarted(tick_count=5))

        mock_build_request.assert_called_once()
        mock_coordinator.dispatch_execution.assert_called_once_with(mock_request)

    @patch("vibe3.services.orchestra_status_service.OrchestraStatusService")
    @patch("vibe3.execution.flow_dispatch.FlowManager")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.models.orchestra_config.OrchestraConfig.from_settings")
    @patch("vibe3.roles.governance.build_governance_request")
    def test_no_dispatch_when_request_is_none(
        self,
        mock_build_request: MagicMock,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_flow_cls: MagicMock,
        mock_status_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.governance_scan import (
            handle_governance_scan_started,
        )

        mock_config = MagicMock(dry_run=False, governance_max_concurrent=1)
        mock_from_settings.return_value = mock_config

        mock_build_request.return_value = None

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        mock_status = MagicMock()
        mock_status.snapshot.return_value = MagicMock(circuit_breaker_state="closed")
        mock_status_cls.return_value = mock_status

        handle_governance_scan_started(GovernanceScanStarted(tick_count=5))

        mock_coordinator.dispatch_execution.assert_not_called()

    @patch("vibe3.services.orchestra_status_service.OrchestraStatusService")
    @patch("vibe3.execution.flow_dispatch.FlowManager")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.models.orchestra_config.OrchestraConfig.from_settings")
    @patch("vibe3.roles.governance.build_governance_request")
    def test_coordinator_failure_logged(
        self,
        mock_build_request: MagicMock,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_flow_cls: MagicMock,
        mock_status_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.governance_scan import (
            handle_governance_scan_started,
        )

        mock_config = MagicMock(dry_run=False, governance_max_concurrent=1)
        mock_from_settings.return_value = mock_config

        mock_request = MagicMock()
        mock_build_request.return_value = mock_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=False, reason="capacity full", reason_code="capacity_full"
        )
        mock_coordinator_cls.return_value = mock_coordinator

        mock_status = MagicMock()
        mock_status.snapshot.return_value = MagicMock(circuit_breaker_state="closed")
        mock_status_cls.return_value = mock_status

        handle_governance_scan_started(GovernanceScanStarted(tick_count=5))

        mock_coordinator.dispatch_execution.assert_called_once()

    @patch("vibe3.services.orchestra_status_service.OrchestraStatusService")
    @patch("vibe3.execution.flow_dispatch.FlowManager")
    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.models.orchestra_config.OrchestraConfig.from_settings")
    @patch("vibe3.roles.governance.build_governance_request")
    def test_exception_during_build_logged(
        self,
        mock_build_request: MagicMock,
        mock_from_settings: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_flow_cls: MagicMock,
        mock_status_cls: MagicMock,
    ) -> None:
        from vibe3.domain.handlers.governance_scan import (
            handle_governance_scan_started,
        )

        mock_config = MagicMock(dry_run=False, governance_max_concurrent=1)
        mock_from_settings.return_value = mock_config

        mock_build_request.side_effect = RuntimeError("snap failed")
        mock_coordinator_cls.return_value = MagicMock()

        mock_status = MagicMock()
        mock_status.snapshot.return_value = MagicMock(circuit_breaker_state="closed")
        mock_status_cls.return_value = mock_status

        handle_governance_scan_started(GovernanceScanStarted(tick_count=5))
