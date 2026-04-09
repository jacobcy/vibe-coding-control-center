"""Tests for governance event handlers.

Tests cover:
- GovernanceScanStarted event handling
- GovernanceService.run_scan() invocation
- ExecutionLifecycleService integration
- CapacityService integration
"""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.governance import GovernanceScanStarted


def _make_governance_scan_started_event(
    tick_count: int = 1,
) -> GovernanceScanStarted:
    """Create a sample GovernanceScanStarted event."""
    return GovernanceScanStarted(tick_count=tick_count)


class TestGovernanceHandlerScanStarted:
    """Test GovernanceScanStarted event handling."""

    @patch("vibe3.domain.handlers.governance.GovernanceService")
    def test_handler_calls_governance_service_run_scan(
        self,
        mock_governance_service_cls: MagicMock,
    ) -> None:
        """Handler should call GovernanceService.run_scan()."""
        from vibe3.domain.handlers.governance import handle_governance_scan_started

        mock_service = MagicMock()
        mock_governance_service_cls.return_value = mock_service

        event = _make_governance_scan_started_event()

        handle_governance_scan_started(event)

        # Verify run_scan was called
        mock_service.run_scan.assert_called_once()

    @patch("vibe3.domain.handlers.governance.GovernanceService")
    @patch("vibe3.domain.handlers.governance.ExecutionLifecycleService")
    @patch("vibe3.domain.handlers.governance.OrchestraConfig")
    def test_handler_uses_lifecycle_service(
        self,
        mock_config_cls: MagicMock,
        mock_lifecycle_cls: MagicMock,
        mock_governance_service_cls: MagicMock,
    ) -> None:
        """Handler should use ExecutionLifecycleService for started event."""
        from vibe3.domain.handlers.governance import handle_governance_scan_started

        mock_config = MagicMock()
        mock_config.governance_max_concurrent = 1
        mock_config_cls.from_settings.return_value = mock_config

        mock_lifecycle = MagicMock()
        mock_lifecycle_cls.return_value = mock_lifecycle

        mock_service = MagicMock()
        mock_governance_service_cls.return_value = mock_service

        event = _make_governance_scan_started_event()

        handle_governance_scan_started(event)

        # Verify lifecycle record_started was called
        mock_lifecycle.record_started.assert_called_once_with(
            role="governance",
            target="governance_scan",
            actor="orchestra:governance",
            refs={},
        )

    @patch("vibe3.domain.handlers.governance.GovernanceService")
    @patch("vibe3.domain.handlers.governance.CapacityService")
    @patch("vibe3.domain.handlers.governance.OrchestraConfig")
    def test_handler_uses_capacity_service(
        self,
        mock_config_cls: MagicMock,
        mock_capacity_cls: MagicMock,
        mock_governance_service_cls: MagicMock,
    ) -> None:
        """Handler should use CapacityService for capacity check."""
        from vibe3.domain.handlers.governance import handle_governance_scan_started

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        mock_service = MagicMock()
        mock_governance_service_cls.return_value = mock_service

        event = _make_governance_scan_started_event()

        handle_governance_scan_started(event)

        # Verify capacity check was called
        mock_capacity.can_dispatch.assert_called_once_with(
            role="governance",
            target_id=1,
        )

    @patch("vibe3.domain.handlers.governance.GovernanceService")
    @patch("vibe3.domain.handlers.governance.CapacityService")
    @patch("vibe3.domain.handlers.governance.OrchestraConfig")
    def test_handler_marks_in_flight_on_start(
        self,
        mock_config_cls: MagicMock,
        mock_capacity_cls: MagicMock,
        mock_governance_service_cls: MagicMock,
    ) -> None:
        """Handler should mark in-flight when starting scan."""
        from vibe3.domain.handlers.governance import handle_governance_scan_started

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        mock_service = MagicMock()
        mock_governance_service_cls.return_value = mock_service

        event = _make_governance_scan_started_event()

        handle_governance_scan_started(event)

        # Verify mark_in_flight was called
        mock_capacity.mark_in_flight.assert_called_once_with(
            role="governance",
            target_id=1,
        )

    @patch("vibe3.domain.handlers.governance.GovernanceService")
    @patch("vibe3.domain.handlers.governance.CapacityService")
    @patch("vibe3.domain.handlers.governance.OrchestraConfig")
    def test_handler_skips_scan_when_capacity_exceeded(
        self,
        mock_config_cls: MagicMock,
        mock_capacity_cls: MagicMock,
        mock_governance_service_cls: MagicMock,
    ) -> None:
        """Handler should skip scan when capacity is not available."""
        from vibe3.domain.handlers.governance import handle_governance_scan_started

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = False
        mock_capacity_cls.return_value = mock_capacity

        mock_service = MagicMock()
        mock_governance_service_cls.return_value = mock_service

        event = _make_governance_scan_started_event()

        handle_governance_scan_started(event)

        # Verify run_scan was NOT called
        mock_service.run_scan.assert_not_called()

        # Verify mark_in_flight was NOT called
        mock_capacity.mark_in_flight.assert_not_called()
