"""Tests for governance event handlers.

Tests cover:
- GovernanceScanStarted event handling
- GovernanceService payload generation
- ExecutionCoordinator dispatch
"""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.governance import GovernanceScanStarted
from vibe3.execution.contracts import ExecutionLaunchResult


def _make_governance_scan_started_event(
    tick_count: int = 1,
) -> GovernanceScanStarted:
    """Create a sample GovernanceScanStarted event."""
    return GovernanceScanStarted(tick_count=tick_count)


class TestGovernanceHandlerScanStarted:
    """Test GovernanceScanStarted event handling."""

    @patch("vibe3.domain.handlers.governance.GovernanceService.from_config")
    @patch("vibe3.domain.handlers.governance.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.governance.OrchestraConfig")
    def test_handler_calls_coordinator_dispatch(
        self,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_service_factory: MagicMock,
    ) -> None:
        """Handler should call ExecutionCoordinator.dispatch_execution()."""
        from vibe3.domain.handlers.governance import handle_governance_scan_started

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True, tmux_session="vibe3-gov-1", log_path="/tmp/gov.log"
        )
        mock_coordinator_cls.return_value = mock_coordinator

        mock_service = MagicMock()
        mock_service.build_execution_name.return_value = "vibe3-gov-scan"

        # Async mock for build_governance_execution_payload
        async def mock_payload():
            return "test prompt", {"agent": "claude"}, "test task"

        mock_service.build_governance_execution_payload.side_effect = mock_payload
        mock_service_factory.return_value = mock_service

        event = _make_governance_scan_started_event()

        # Run synchronously since the handler wraps it in asyncio.run
        handle_governance_scan_started(event)

        # Verify payload generation was called
        mock_service.build_governance_execution_payload.assert_called_once()

        # Verify coordinator dispatch was called
        mock_coordinator.dispatch_execution.assert_called_once()
        request = mock_coordinator.dispatch_execution.call_args[0][0]

        assert request.role == "governance"
        assert request.target_id == 1
        assert request.target_branch == "governance"
        assert request.execution_name == "vibe3-gov-scan"
        assert request.prompt == "test prompt"
        assert request.options == {"agent": "claude"}
        assert request.refs["task"] == "test task"
        assert request.mode == "async"

    @patch("vibe3.domain.handlers.governance.GovernanceService.from_config")
    @patch("vibe3.domain.handlers.governance.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.governance.OrchestraConfig")
    def test_handler_skips_when_no_payload(
        self,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_service_factory: MagicMock,
    ) -> None:
        """Handler should skip dispatch when GovernanceService returns empty payload."""
        from vibe3.domain.handlers.governance import handle_governance_scan_started

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        mock_service = MagicMock()

        # Return empty prompt (e.g. circuit breaker open or dry run)
        async def mock_payload():
            return None, None, ""

        mock_service.build_governance_execution_payload.side_effect = mock_payload
        mock_service_factory.return_value = mock_service

        event = _make_governance_scan_started_event()

        handle_governance_scan_started(event)

        mock_service.build_governance_execution_payload.assert_called_once()
        # Verify dispatch was skipped
        mock_coordinator.dispatch_execution.assert_not_called()
