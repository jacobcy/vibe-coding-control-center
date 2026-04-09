"""Tests for supervisor apply event handlers.

Tests cover:
- SupervisorApplyDispatched event handling
- ExecutionCoordinator dispatch
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vibe3.domain.events.supervisor_apply import SupervisorApplyDispatched
from vibe3.execution.contracts import ExecutionLaunchResult


def _make_supervisor_apply_dispatched_event() -> SupervisorApplyDispatched:
    return SupervisorApplyDispatched(
        issue_number=42,
        tmux_session="vibe-supervisor-42",
        supervisor_file="supervisor/apply.md",
        actor="agent:supervisor",
    )


class TestSupervisorApplyHandlerDispatch:
    """Test SupervisorApplyDispatched event handling."""

    @patch(
        "vibe3.domain.handlers.supervisor_apply.SupervisorHandoffService.from_config"
    )
    @patch("vibe3.domain.handlers.supervisor_apply.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_apply.OrchestraConfig")
    def test_handler_calls_coordinator(
        self,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_service_factory: MagicMock,
    ) -> None:
        """Handler should call ExecutionCoordinator."""
        from vibe3.domain.handlers.supervisor_apply import (
            handle_supervisor_apply_dispatched,
        )

        mock_config = MagicMock()
        mock_config.dry_run = False
        mock_config_cls.from_settings.return_value = mock_config

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = ExecutionLaunchResult(
            launched=True, tmux_session="vibe-supervisor-42"
        )
        mock_coordinator_cls.return_value = mock_coordinator

        mock_service = MagicMock()
        wt_context = MagicMock()
        wt_context.path = "/tmp/wt"
        mock_service.acquire_temporary_worktree.return_value = wt_context

        mock_service.build_handoff_payload.return_value = (
            "test prompt",
            {"agent": "claude"},
            "test task",
        )
        mock_service_factory.return_value = mock_service

        event = _make_supervisor_apply_dispatched_event()

        handle_supervisor_apply_dispatched(event)

        mock_service.build_handoff_payload.assert_called_once()
        mock_coordinator.dispatch_execution.assert_called_once()

        request = mock_coordinator.dispatch_execution.call_args[0][0]
        assert request.role == "supervisor"
        assert request.target_id == 42
        assert request.target_branch == "issue-42"
        assert request.prompt == "test prompt"
        assert request.cwd == "/tmp/wt"

    @patch(
        "vibe3.domain.handlers.supervisor_apply.SupervisorHandoffService.from_config"
    )
    @patch("vibe3.domain.handlers.supervisor_apply.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_apply.OrchestraConfig")
    def test_handler_skips_on_dry_run(
        self,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_service_factory: MagicMock,
    ) -> None:
        """Handler should skip dispatch on dry run."""
        from vibe3.domain.handlers.supervisor_apply import (
            handle_supervisor_apply_dispatched,
        )

        mock_config = MagicMock()
        mock_config.dry_run = True
        mock_config_cls.from_settings.return_value = mock_config

        mock_coordinator = MagicMock()
        mock_coordinator_cls.return_value = mock_coordinator

        mock_service = MagicMock()
        mock_service_factory.return_value = mock_service

        event = _make_supervisor_apply_dispatched_event()

        handle_supervisor_apply_dispatched(event)

        mock_service.build_handoff_payload.assert_not_called()
        mock_coordinator.dispatch_execution.assert_not_called()

    @pytest.mark.asyncio
    @patch(
        "vibe3.domain.handlers.supervisor_apply.asyncio.to_thread",
        new_callable=AsyncMock,
    )
    async def test_handler_uses_to_thread_when_loop_is_running(
        self,
        mock_to_thread: AsyncMock,
    ) -> None:
        """Handler should offload blocking supervisor dispatch to a worker thread."""
        from vibe3.domain.handlers.supervisor_apply import (
            handle_supervisor_apply_dispatched,
        )

        event = _make_supervisor_apply_dispatched_event()

        handle_supervisor_apply_dispatched(event)
        await asyncio.sleep(0)

        mock_to_thread.assert_called_once()
