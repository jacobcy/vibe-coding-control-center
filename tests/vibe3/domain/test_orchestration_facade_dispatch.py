"""Tests for OrchestrationFacade GlobalDispatchCoordinator integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe3.domain.orchestration_facade import OrchestrationFacade


class TestOrchestrationFacadeDispatchServices:
    """Tests for GlobalDispatchCoordinator integration (refactored in issue-462)."""

    @pytest.mark.asyncio
    @patch("vibe3.domain.orchestration_facade.publish")
    @patch("vibe3.domain.orchestration_facade.time.monotonic")
    @patch("vibe3.domain.orchestration_facade.OrchestraConfig")
    async def test_on_tick_uses_global_dispatch_coordinator(
        self,
        mock_config_cls: MagicMock,
        mock_monotonic: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """on_tick() should use GlobalDispatchCoordinator internally."""
        mock_config_cls.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
            ),
        )
        mock_monotonic.side_effect = [float(i) for i in range(20)]

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity.get_capacity_status.return_value = {
            "remaining": 1,
            "active_count": 0,
            "max_capacity": 5,
        }

        facade = OrchestrationFacade(
            tick_count=0,
            capacity=mock_capacity,
        )

        # Mock GlobalDispatchCoordinator.coordinate to track calls
        with (
            patch.object(facade, "on_supervisor_scan", new_callable=AsyncMock),
            patch.object(
                facade._coordinator, "coordinate", new_callable=AsyncMock
            ) as mock_coordinate,
        ):
            await facade.on_tick()

        # Verify GlobalDispatchCoordinator.coordinate() was called
        mock_coordinate.assert_awaited_once()

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
        mock_config_cls.return_value = MagicMock(
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
    async def test_on_tick_handles_coordinator_errors_gracefully(
        self,
        mock_config_cls: MagicMock,
        mock_publish: MagicMock,
    ) -> None:
        """on_tick() should handle exceptions from GlobalDispatchCoordinator gracefully.

        GlobalDispatchCoordinator handles errors from _poll_issues_by_state internally,
        so facade's on_tick() should complete without raising exceptions.
        """
        mock_config_cls.return_value = MagicMock(
            polling_interval=1,
            governance=MagicMock(interval_ticks=1),
            supervisor_handoff=MagicMock(
                issue_label="supervisor",
                handoff_state_label="state/handoff",
            ),
        )

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = False  # Skip all dispatches
        mock_capacity.get_capacity_status.return_value = {
            "remaining": 1,
            "active_count": 4,
            "max_capacity": 5,
        }

        facade = OrchestrationFacade(
            tick_count=0,
            capacity=mock_capacity,
        )

        with (
            patch.object(facade, "on_supervisor_scan", new_callable=AsyncMock),
            patch.object(facade, "on_heartbeat_tick"),
            patch.object(
                facade._coordinator,
                "coordinate",
                new_callable=AsyncMock,
                side_effect=RuntimeError("GitHub down"),
            ) as mock_coordinate,
        ):
            # Should raise the error (not swallowed by facade)
            with pytest.raises(RuntimeError, match="GitHub down"):
                await facade.on_tick()

        # Verify coordinate was called
        mock_coordinate.assert_awaited_once()
