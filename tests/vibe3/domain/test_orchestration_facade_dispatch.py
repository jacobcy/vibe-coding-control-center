"""Tests for OrchestrationFacade dispatch_services integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe3.domain.orchestration_facade import OrchestrationFacade
from vibe3.models.orchestration import IssueState


class TestOrchestrationFacadeDispatchServices:
    """Tests for dispatch_services integration (P2: unified heartbeat registration)."""

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    async def test_on_tick_calls_all_dispatch_services(
        self,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """on_tick() should use GlobalDispatchCoordinator to coordinate dispatch."""
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
            ),
        )
        mock_monotonic.side_effect = [float(i) for i in range(20)]

        mock_service1 = MagicMock()
        mock_service1.role_def = MagicMock()
        mock_service1.role_def.trigger_state = IssueState.REVIEW
        mock_service1.collect_ready_issues = AsyncMock(return_value=[])
        mock_service2 = MagicMock()
        mock_service2.role_def = MagicMock()
        mock_service2.role_def.trigger_state = IssueState.IN_PROGRESS
        mock_service2.collect_ready_issues = AsyncMock(return_value=[])

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity.get_capacity_status.return_value = {
            "remaining": 1,
            "active_count": 0,
            "max_capacity": 5,
        }

        facade = OrchestrationFacade(
            tick_count=0,
            dispatch_services=[mock_service1, mock_service2],
            capacity=mock_capacity,
        )

        with patch.object(facade, "on_supervisor_scan", new_callable=AsyncMock):
            await facade.on_tick()

        # Verify GlobalDispatchCoordinator is used (via collect_ready_issues)
        mock_service1.collect_ready_issues.assert_awaited_once()
        mock_service2.collect_ready_issues.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    async def test_on_tick_no_dispatch_services_by_default(
        self,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """on_tick() should work normally when no dispatch_services are provided."""
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
            ),
        )
        mock_monotonic.side_effect = [float(i) for i in range(20)]

        facade = OrchestrationFacade(tick_count=0)

        with patch.object(facade, "on_supervisor_scan", new_callable=AsyncMock):
            await facade.on_tick()

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    async def test_on_tick_continues_when_collect_fails(
        self,
        mock_config_cls: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """on_tick() should handle exceptions from collect_ready_issues gracefully.

        GlobalDispatchCoordinator handles errors from collect_ready_issues() internally,
        so facade's on_tick() should complete without raising exceptions.
        """
        mock_config_cls.from_settings.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
            ),
        )

        failing_service = MagicMock()
        failing_service.service_name = "failing-dispatch"
        failing_service.role_def = MagicMock()
        failing_service.role_def.trigger_state = IssueState.REVIEW
        failing_service.collect_ready_issues = AsyncMock(
            side_effect=RuntimeError("GitHub down")
        )
        healthy_service = MagicMock()
        healthy_service.service_name = "healthy-dispatch"
        healthy_service.role_def = MagicMock()
        healthy_service.role_def.trigger_state = IssueState.IN_PROGRESS
        healthy_service.collect_ready_issues = AsyncMock(return_value=[])

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = False  # Skip all dispatches
        mock_capacity.get_capacity_status.return_value = {
            "remaining": 1,
            "active_count": 4,
            "max_capacity": 5,
        }

        facade = OrchestrationFacade(
            tick_count=0,
            dispatch_services=[failing_service, healthy_service],
            capacity=mock_capacity,
        )

        with (
            patch.object(facade, "on_supervisor_scan", new_callable=AsyncMock),
            patch.object(facade, "on_heartbeat_tick"),
        ):
            # Should not raise, GlobalDispatchCoordinator handles errors internally
            await facade.on_tick()

        # Both services should be called for collection
        failing_service.collect_ready_issues.assert_awaited_once()
        healthy_service.collect_ready_issues.assert_awaited_once()
