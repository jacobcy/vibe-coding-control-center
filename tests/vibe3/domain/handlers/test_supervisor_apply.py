"""Tests for supervisor apply event handlers.

Tests cover:
- SupervisorApplyDispatched event handling
- ExecutionCoordinator dispatch
"""

from unittest.mock import MagicMock, patch

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

    @patch("vibe3.domain.handlers.supervisor_apply.SupervisorHandoffService")
    @patch("vibe3.domain.handlers.supervisor_apply.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_apply.OrchestraConfig")
    @patch("vibe3.environment.worktree.WorktreeManager")
    def test_handler_calls_coordinator(
        self,
        mock_worktree_manager_cls: MagicMock,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_supervisor_service_cls: MagicMock,
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

        mock_worktree_manager = MagicMock()
        mock_worktree_manager.acquire_temporary_worktree.return_value = wt_context
        mock_worktree_manager_cls.return_value = mock_worktree_manager

        mock_service.build_handoff_payload.return_value = (
            "test prompt",
            {"agent": "claude"},
            "test task",
        )
        mock_supervisor_service_cls.return_value = mock_service

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

    @patch("vibe3.domain.handlers.supervisor_apply.SupervisorHandoffService")
    @patch("vibe3.domain.handlers.supervisor_apply.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.supervisor_apply.OrchestraConfig")
    def test_handler_skips_on_dry_run(
        self,
        mock_config_cls: MagicMock,
        mock_coordinator_cls: MagicMock,
        mock_supervisor_service_cls: MagicMock,
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
        mock_supervisor_service_cls.return_value = mock_service

        event = _make_supervisor_apply_dispatched_event()

        handle_supervisor_apply_dispatched(event)

        mock_service.build_handoff_payload.assert_not_called()
        mock_coordinator.dispatch_execution.assert_not_called()
