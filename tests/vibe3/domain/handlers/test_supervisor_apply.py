"""Tests for supervisor apply event handlers.

Tests cover:
- SupervisorApplyDispatched event handling
- SupervisorHandoffService invocation
- ExecutionLifecycleService integration
- CapacityService integration
"""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.supervisor_apply import SupervisorApplyDispatched


def _make_supervisor_apply_dispatched_event(
    issue_number: int = 42,
    tmux_session: str = "vibe-supervisor-42",
    supervisor_file: str = "supervisor/apply.md",
) -> SupervisorApplyDispatched:
    """Create a sample SupervisorApplyDispatched event."""
    return SupervisorApplyDispatched(
        issue_number=issue_number,
        tmux_session=tmux_session,
        supervisor_file=supervisor_file,
    )


class TestSupervisorApplyHandlerDispatch:
    """Test SupervisorApplyDispatched event handling."""

    @patch("vibe3.domain.handlers.supervisor_apply.SupervisorHandoffService")
    def test_handler_calls_supervisor_handoff_service(
        self,
        mock_supervisor_service_cls: MagicMock,
    ) -> None:
        """Handler should call SupervisorHandoffService."""
        from vibe3.domain.handlers.supervisor_apply import (
            handle_supervisor_apply_dispatched,
        )

        mock_service = MagicMock()
        mock_supervisor_service_cls.return_value = mock_service

        event = _make_supervisor_apply_dispatched_event()

        handle_supervisor_apply_dispatched(event)

        # Verify handoff service was invoked
        mock_service.dispatch_handoff.assert_called_once()

    @patch("vibe3.domain.handlers.supervisor_apply.SupervisorHandoffService")
    @patch("vibe3.domain.handlers.supervisor_apply.ExecutionLifecycleService")
    @patch("vibe3.domain.handlers.supervisor_apply.OrchestraConfig")
    def test_handler_uses_lifecycle_service(
        self,
        mock_config_cls: MagicMock,
        mock_lifecycle_cls: MagicMock,
        mock_supervisor_service_cls: MagicMock,
    ) -> None:
        """Handler should use ExecutionLifecycleService for started event."""
        from vibe3.domain.handlers.supervisor_apply import (
            handle_supervisor_apply_dispatched,
        )

        mock_config = MagicMock()
        mock_config.max_concurrent_flows = 3
        mock_config.supervisor_max_concurrent = 2
        mock_config.governance_max_concurrent = 1
        mock_config_cls.from_settings.return_value = mock_config

        mock_lifecycle = MagicMock()
        mock_lifecycle_cls.return_value = mock_lifecycle

        mock_service = MagicMock()
        mock_supervisor_service_cls.return_value = mock_service

        event = _make_supervisor_apply_dispatched_event()

        handle_supervisor_apply_dispatched(event)

        # Verify lifecycle record_started was called
        mock_lifecycle.record_started.assert_called_once_with(
            role="supervisor",
            target="issue-42",
            actor="orchestra:supervisor",
            refs={
                "issue_number": "42",
                "tmux_session": "vibe-supervisor-42",
            },
        )
        mock_lifecycle.record_completed.assert_not_called()

    @patch("vibe3.domain.handlers.supervisor_apply.SupervisorHandoffService")
    @patch("vibe3.domain.handlers.supervisor_apply.CapacityService")
    @patch("vibe3.domain.handlers.supervisor_apply.OrchestraConfig")
    def test_handler_uses_capacity_service(
        self,
        mock_config_cls: MagicMock,
        mock_capacity_cls: MagicMock,
        mock_supervisor_service_cls: MagicMock,
    ) -> None:
        """Handler should use CapacityService for capacity check."""
        from vibe3.domain.handlers.supervisor_apply import (
            handle_supervisor_apply_dispatched,
        )

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        mock_service = MagicMock()
        mock_supervisor_service_cls.return_value = mock_service

        event = _make_supervisor_apply_dispatched_event()

        handle_supervisor_apply_dispatched(event)

        # Verify capacity check was called
        mock_capacity.can_dispatch.assert_called_once_with(
            role="supervisor",
            target_id=42,
        )

    @patch("vibe3.domain.handlers.supervisor_apply.SupervisorHandoffService")
    @patch("vibe3.domain.handlers.supervisor_apply.CapacityService")
    @patch("vibe3.domain.handlers.supervisor_apply.OrchestraConfig")
    def test_handler_marks_in_flight_on_start(
        self,
        mock_config_cls: MagicMock,
        mock_capacity_cls: MagicMock,
        mock_supervisor_service_cls: MagicMock,
    ) -> None:
        """Handler should mark in-flight when starting handoff."""
        from vibe3.domain.handlers.supervisor_apply import (
            handle_supervisor_apply_dispatched,
        )

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity

        mock_service = MagicMock()
        mock_supervisor_service_cls.return_value = mock_service

        event = _make_supervisor_apply_dispatched_event()

        handle_supervisor_apply_dispatched(event)

        # Verify mark_in_flight was called
        mock_capacity.mark_in_flight.assert_called_once_with(
            role="supervisor",
            target_id=42,
        )

    @patch("vibe3.domain.handlers.supervisor_apply.SupervisorHandoffService")
    @patch("vibe3.domain.handlers.supervisor_apply.CapacityService")
    @patch("vibe3.domain.handlers.supervisor_apply.OrchestraConfig")
    def test_handler_skips_handoff_when_capacity_exceeded(
        self,
        mock_config_cls: MagicMock,
        mock_capacity_cls: MagicMock,
        mock_supervisor_service_cls: MagicMock,
    ) -> None:
        """Handler should skip handoff when capacity is not available."""
        from vibe3.domain.handlers.supervisor_apply import (
            handle_supervisor_apply_dispatched,
        )

        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = False
        mock_capacity_cls.return_value = mock_capacity

        mock_service = MagicMock()
        mock_supervisor_service_cls.return_value = mock_service

        event = _make_supervisor_apply_dispatched_event()

        handle_supervisor_apply_dispatched(event)

        # Verify dispatch_handoff was NOT called
        mock_service.dispatch_handoff.assert_not_called()

        # Verify mark_in_flight was NOT called
        mock_capacity.mark_in_flight.assert_not_called()

    @patch("vibe3.domain.handlers.supervisor_apply.SupervisorHandoffService")
    @patch("vibe3.domain.handlers.supervisor_apply.GitHubClient")
    @patch("vibe3.domain.handlers.supervisor_apply.CapacityService")
    @patch("vibe3.domain.handlers.supervisor_apply.ExecutionLifecycleService")
    @patch("vibe3.domain.handlers.supervisor_apply.OrchestraConfig")
    def test_comment_failure_does_not_mark_dispatch_failed(
        self,
        mock_config_cls: MagicMock,
        mock_lifecycle_cls: MagicMock,
        mock_capacity_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_supervisor_service_cls: MagicMock,
    ) -> None:
        """Post-launch comment failure should not rewrite lifecycle as failed."""
        from vibe3.domain.handlers.supervisor_apply import (
            handle_supervisor_apply_dispatched,
        )

        mock_config_cls.from_settings.return_value = MagicMock()
        mock_lifecycle = MagicMock()
        mock_lifecycle_cls.return_value = mock_lifecycle
        mock_capacity = MagicMock()
        mock_capacity.can_dispatch.return_value = True
        mock_capacity_cls.return_value = mock_capacity
        mock_github = MagicMock()
        mock_github.add_comment.side_effect = RuntimeError("comment failed")
        mock_github_cls.return_value = mock_github
        mock_service = MagicMock()
        mock_supervisor_service_cls.return_value = mock_service

        handle_supervisor_apply_dispatched(_make_supervisor_apply_dispatched_event())

        mock_service.dispatch_handoff.assert_called_once()
        mock_lifecycle.record_started.assert_called_once()
        mock_lifecycle.record_failed.assert_not_called()
