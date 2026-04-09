"""Tests for manager event handlers.

Tests cover:
- Guard logic (only handle 'claimed' state)
- GitHub issue fetching
- ManagerExecutor dispatch
"""

from unittest.mock import MagicMock, patch

from vibe3.domain.events.flow_lifecycle import IssueStateChanged
from vibe3.domain.handlers.manager import handle_issue_state_changed_for_manager
from vibe3.models.orchestration import IssueInfo, IssueState


def _make_event(
    issue_number: int = 42,
    from_state: str | None = "ready",
    to_state: str = "claimed",
) -> IssueStateChanged:
    """Create a sample IssueStateChanged event."""
    return IssueStateChanged(
        issue_number=issue_number,
        from_state=from_state,
        to_state=to_state,
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
        "labels": [{"name": "state/claimed"}],
        "assignees": [],
        "milestone": None,
    }


class TestManagerHandlerGuardLogic:
    """Test guard: only handle 'claimed' state."""

    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_ignores_non_claimed_state(
        self,
        mock_config_cls: MagicMock,
    ) -> None:
        """Handler should return early when to_state is not 'claimed'."""
        mock_config_cls.from_settings.return_value = MagicMock()

        event = _make_event(to_state="in-progress")

        # Should not raise and should not create any services
        handle_issue_state_changed_for_manager(event)

        # No services should be created for non-claimed states
        mock_config_cls.from_settings.assert_not_called()

    @patch("vibe3.domain.handlers.manager.ManagerExecutor")
    @patch("vibe3.domain.handlers.manager.GitHubClient")
    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_processes_claimed_state(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """Handler should process events with to_state='claimed'."""
        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_github = MagicMock()
        mock_github.view_issue.return_value = _make_github_response()
        mock_github_cls.return_value = mock_github

        mock_executor = MagicMock()
        mock_executor.dispatch_manager.return_value = True
        mock_executor_cls.return_value = mock_executor

        event = _make_event(to_state="claimed")

        with patch(
            "vibe3.domain.handlers.manager.IssueInfo.from_github_payload"
        ) as mock_from_payload:
            mock_from_payload.return_value = IssueInfo(
                number=42,
                title="Test issue",
                state=IssueState.CLAIMED,
            )
            handle_issue_state_changed_for_manager(event)

        mock_executor.dispatch_manager.assert_called_once()


class TestManagerHandlerIssueFetching:
    """Test GitHub issue fetching and error handling."""

    @patch("vibe3.domain.handlers.manager.ManagerExecutor")
    @patch("vibe3.domain.handlers.manager.GitHubClient")
    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_records_failed_on_github_none(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """Handler should skip dispatch when GitHub returns None."""
        mock_config_cls.from_settings.return_value = MagicMock()

        mock_github = MagicMock()
        mock_github.view_issue.return_value = None
        mock_github_cls.return_value = mock_github

        event = _make_event()
        handle_issue_state_changed_for_manager(event)

        # Should NOT dispatch
        mock_executor_cls.assert_not_called()

    @patch("vibe3.domain.handlers.manager.ManagerExecutor")
    @patch("vibe3.domain.handlers.manager.GitHubClient")
    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_records_failed_on_network_error(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """Handler should skip dispatch when GitHub returns network error."""
        mock_config_cls.from_settings.return_value = MagicMock()

        mock_github = MagicMock()
        mock_github.view_issue.return_value = "network_error"
        mock_github_cls.return_value = mock_github

        event = _make_event()
        handle_issue_state_changed_for_manager(event)

        # Should NOT dispatch
        mock_executor_cls.assert_not_called()

    @patch("vibe3.domain.handlers.manager.ManagerExecutor")
    @patch("vibe3.domain.handlers.manager.GitHubClient")
    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_records_failed_on_invalid_issue_data(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """Handler should skip dispatch when from_github_payload returns None."""
        mock_config_cls.from_settings.return_value = MagicMock()

        mock_github = MagicMock()
        mock_github.view_issue.return_value = _make_github_response()
        mock_github_cls.return_value = mock_github

        event = _make_event()

        with patch(
            "vibe3.domain.handlers.manager.IssueInfo.from_github_payload",
            return_value=None,
        ):
            handle_issue_state_changed_for_manager(event)

        # Should NOT dispatch
        mock_executor_cls.assert_not_called()


class TestManagerHandlerDispatch:
    """Test ManagerExecutor dispatch."""

    @patch("vibe3.domain.handlers.manager.ManagerExecutor")
    @patch("vibe3.domain.handlers.manager.GitHubClient")
    @patch("vibe3.domain.handlers.manager.OrchestraConfig")
    def test_dispatch_success(
        self,
        mock_config_cls: MagicMock,
        mock_github_cls: MagicMock,
        mock_executor_cls: MagicMock,
    ) -> None:
        """Handler should call dispatch."""
        mock_config = MagicMock()
        mock_config_cls.from_settings.return_value = mock_config

        mock_github = MagicMock()
        mock_github.view_issue.return_value = _make_github_response()
        mock_github_cls.return_value = mock_github

        mock_executor = MagicMock()
        mock_executor.dispatch_manager.return_value = True
        mock_executor_cls.return_value = mock_executor

        event = _make_event()

        with patch(
            "vibe3.domain.handlers.manager.IssueInfo.from_github_payload"
        ) as mock_from_payload:
            mock_from_payload.return_value = IssueInfo(
                number=42,
                title="Test issue",
                state=IssueState.CLAIMED,
            )
            handle_issue_state_changed_for_manager(event)

        # Verify dispatch was called with IssueInfo
        mock_executor.dispatch_manager.assert_called_once()
