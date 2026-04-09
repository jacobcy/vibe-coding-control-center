"""Tests for supervisor issue identification wiring."""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.supervisor_apply import SupervisorApplyDispatched


class TestSupervisorIssueIdentifiedHandler:
    """Supervisor identification should promote into apply dispatch."""

    @patch("vibe3.domain.handlers.supervisor_apply.publish")
    def test_identified_event_promotes_to_apply_dispatch(
        self,
        mock_publish: MagicMock,
    ) -> None:
        from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
        from vibe3.domain.handlers.supervisor_apply import (
            handle_supervisor_issue_identified,
        )

        handle_supervisor_issue_identified(
            SupervisorIssueIdentified(
                issue_number=42,
                issue_title="Need supervisor help",
                supervisor_file="supervisor/apply.md",
            )
        )

        mock_publish.assert_called_once()
        event = mock_publish.call_args.args[0]
        assert isinstance(event, SupervisorApplyDispatched)
        assert event.issue_number == 42
        assert event.supervisor_file == "supervisor/apply.md"
        assert event.tmux_session == "vibe3-supervisor-issue-42"
