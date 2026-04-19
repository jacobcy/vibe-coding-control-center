"""Tests for manager dispatch-intent handler.

Tests cover:
- Guard logic (only handle ready/handoff trigger states)
- Skip logic for human:resume actor
- Fast path: event carries issue_title, no GitHub fetch needed
- Slow path: event missing issue_title, falls back to view_issue
- Manager role dispatch via ExecutionCoordinator
"""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.flow_lifecycle import ManagerDispatched
from vibe3.domain.handlers.issue_state_dispatch import handle_manager_dispatched
from vibe3.models.orchestration import IssueState


def _make_event(
    issue_number: int = 42,
    trigger_state: str = "ready",
    branch: str = "task/issue-42",
    issue_title: str | None = None,
    actor: str = "orchestra:dispatcher",
) -> ManagerDispatched:
    """Create a sample ManagerDispatched event."""
    return ManagerDispatched(
        issue_number=issue_number,
        branch=branch,
        trigger_state=trigger_state,
        issue_title=issue_title,
        actor=actor,
    )


def _make_github_response(
    number: int = 42,
    title: str = "Test issue",
    state: str = "open",
) -> dict:
    """Create a sample GitHub API response."""
    return {
        "number": number,
        "title": title,
        "state": state,
        "body": "Test body",
        "labels": [{"name": "state/ready"}],
        "assignees": [],
        "milestone": None,
    }


class TestManagerHandlerGuardLogic:
    """Test guard: only handle ready/handoff trigger states."""

    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    def test_ignores_non_manager_trigger_state(
        self,
        mock_config_cls: MagicMock,
    ) -> None:
        """Handler should return early when trigger_state is not ready/handoff."""
        mock_config_cls.from_settings.return_value = MagicMock()

        event = _make_event(trigger_state="in-progress")

        # Should not raise and should not create any services
        handle_manager_dispatched(event)

        # No services should be created for non-trigger states
        mock_config_cls.from_settings.assert_not_called()

    def test_skips_human_resume_actor(self) -> None:
        """Handler should skip dispatch for human:resume actor."""
        event = _make_event(actor="human:resume")

        # Should not raise and should not create any services
        handle_manager_dispatched(event)


class TestManagerHandlerIssueFetching:
    """Test slow-path GitHub issue fetching and error handling.

    These tests exercise the fallback when event.issue_title is None
    (i.e., events that don't carry the title).
    """

    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    def test_records_failed_on_github_none(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        """Handler should skip dispatch when GitHub returns None (slow path)."""
        mock_config_cls.from_settings.return_value = MagicMock()

        mock_github = MagicMock()
        mock_github.view_issue.return_value = None
        mock_github_cls.return_value = mock_github

        # No issue_title triggers slow path
        event = _make_event(issue_title=None)
        handle_manager_dispatched(event)

        # Should NOT dispatch
        mock_build_request.assert_not_called()

    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    def test_records_failed_on_network_error(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        """Handler should skip dispatch when GitHub returns network error."""
        mock_config_cls.from_settings.return_value = MagicMock()

        mock_github = MagicMock()
        mock_github.view_issue.return_value = "network_error"
        mock_github_cls.return_value = mock_github

        event = _make_event(issue_title=None)
        handle_manager_dispatched(event)

        mock_build_request.assert_not_called()

    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    def test_records_failed_on_invalid_issue_data(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        """Handler should skip dispatch when from_github_payload returns None."""
        mock_config_cls.from_settings.return_value = MagicMock()

        mock_github = MagicMock()
        mock_github.view_issue.return_value = _make_github_response()
        mock_github_cls.return_value = mock_github

        event = _make_event(issue_title=None)

        with patch(
            "vibe3.models.orchestration.IssueInfo.from_github_payload",
            return_value=None,
        ):
            handle_manager_dispatched(event)

        mock_build_request.assert_not_called()


class TestManagerHandlerDispatch:
    """Test manager role service dispatch via fast path (issue_title present)."""

    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.issue_state_dispatch.build_manager_request")
    @patch("vibe3.domain.handlers.issue_state_dispatch.OrchestraConfig")
    def test_dispatch_success(
        self,
        mock_config_cls: MagicMock,
        mock_build_request: MagicMock,
        mock_coordinator_cls: MagicMock,
    ) -> None:
        """Handler should dispatch manager with correct IssueInfo via fast path."""
        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_request = MagicMock()
        mock_request.role = "manager"
        mock_build_request.return_value = mock_request

        mock_coordinator = MagicMock()
        mock_coordinator.dispatch_execution.return_value = MagicMock(
            launched=True, reason=None
        )
        mock_coordinator_cls.return_value = mock_coordinator

        # Provide issue_title to use the fast path
        event = _make_event(issue_title="Test issue")

        handle_manager_dispatched(event)

        # Verify build_manager_request was called
        mock_build_request.assert_called_once()
        call_args = mock_build_request.call_args
        dispatched_issue = call_args[0][1]
        assert dispatched_issue.number == 42
        assert dispatched_issue.title == "Test issue"
        assert dispatched_issue.state == IssueState.READY
