"""Tests for manager event handlers.

Tests cover:
- Guard logic (only handle manager trigger states)
- Fast path: event carries issue_title, no GitHub fetch needed
- Slow path: event missing issue_title, falls back to view_issue
- manager role service dispatch
"""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.flow_lifecycle import IssueStateChanged
from vibe3.domain.handlers.manager import handle_issue_state_changed_for_manager
from vibe3.models.orchestration import IssueState


def _make_event(
    issue_number: int = 42,
    from_state: str | None = "blocked",
    to_state: str = "ready",
    issue_title: str | None = None,
) -> IssueStateChanged:
    """Create a sample IssueStateChanged event."""
    return IssueStateChanged(
        issue_number=issue_number,
        from_state=from_state,
        to_state=to_state,
        issue_title=issue_title,
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
    """Test guard: only handle manager trigger states."""

    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_ignores_non_manager_trigger_state(
        self,
        mock_config_cls: MagicMock,
    ) -> None:
        """Handler should return early when to_state is not ready/handoff."""
        mock_config_cls.from_settings.return_value = MagicMock()

        event = _make_event(to_state="claimed")

        # Should not raise and should not create any services
        handle_issue_state_changed_for_manager(event)

        # No services should be created for non-claimed states
        mock_config_cls.from_settings.assert_not_called()

    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.manager.build_manager_dispatch_request")
    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_processes_ready_state(
        self,
        mock_config_cls: MagicMock,
        mock_build_request: MagicMock,
        mock_coordinator_cls: MagicMock,
    ) -> None:
        """Handler should process events with to_state='ready' via fast path."""
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

        # Provide issue_title to use the fast path (no view_issue call)
        event = _make_event(to_state="ready", issue_title="Test issue")

        handle_issue_state_changed_for_manager(event)

        mock_build_request.assert_called_once()
        mock_coordinator.dispatch_execution.assert_called_once()


class TestManagerHandlerIssueFetching:
    """Test slow-path GitHub issue fetching and error handling.

    These tests exercise the fallback when event.issue_title is None
    (i.e., webhook-triggered events that don't carry the title).
    """

    @patch("vibe3.domain.handlers.manager.build_manager_dispatch_request")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
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

        # No issue_title → slow path → calls view_issue
        event = _make_event(issue_title=None)
        handle_issue_state_changed_for_manager(event)

        # Should NOT dispatch
        mock_build_request.assert_not_called()

    @patch("vibe3.domain.handlers.manager.build_manager_dispatch_request")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_records_failed_on_network_error(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        """Handler should skip dispatch when GitHub returns network error
        (slow path)."""
        mock_config_cls.from_settings.return_value = MagicMock()

        mock_github = MagicMock()
        mock_github.view_issue.return_value = "network_error"
        mock_github_cls.return_value = mock_github

        event = _make_event(issue_title=None)
        handle_issue_state_changed_for_manager(event)

        mock_build_request.assert_not_called()

    @patch("vibe3.domain.handlers.manager.build_manager_dispatch_request")
    @patch("vibe3.clients.github_client.GitHubClient")
    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_records_failed_on_invalid_issue_data(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_build_request: MagicMock,
    ) -> None:
        """Handler should skip dispatch when from_github_payload returns
        None (slow path)."""
        mock_config_cls.from_settings.return_value = MagicMock()

        mock_github = MagicMock()
        mock_github.view_issue.return_value = _make_github_response()
        mock_github_cls.return_value = mock_github

        event = _make_event(issue_title=None)

        with patch(
            "vibe3.models.orchestration.IssueInfo.from_github_payload",
            return_value=None,
        ):
            handle_issue_state_changed_for_manager(event)

        mock_build_request.assert_not_called()


class TestManagerHandlerDispatch:
    """Test manager role service dispatch via fast path (issue_title present)."""

    @patch("vibe3.execution.coordinator.ExecutionCoordinator")
    @patch("vibe3.domain.handlers.manager.build_manager_dispatch_request")
    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_dispatch_success(
        self,
        mock_config_cls: MagicMock,
        mock_build_request: MagicMock,
        mock_coordinator_cls: MagicMock,
    ) -> None:
        """Handler should call prepare_execution_request with correct IssueInfo."""
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

        event = _make_event(issue_title="Test issue")

        handle_issue_state_changed_for_manager(event)

        # Verify prepare_execution_request was called with IssueInfo
        mock_build_request.assert_called_once()
        dispatched_issue = mock_build_request.call_args[0][1]
        assert dispatched_issue.number == 42
        assert dispatched_issue.title == "Test issue"
        assert dispatched_issue.state == IssueState.READY
