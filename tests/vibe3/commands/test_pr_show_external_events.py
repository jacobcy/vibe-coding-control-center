"""Integration tests for PR show external event recording."""

from unittest.mock import MagicMock

from vibe3.commands.pr_query import _fetch_and_record_external_events
from vibe3.models.pr import PRResponse


def test_fetch_and_record_external_events_happy_path() -> None:
    """Test successful recording of CI status and comments."""
    # Setup mocks
    mock_github = MagicMock()
    mock_handoff = MagicMock()

    # Mock PR with CI status
    mock_pr = MagicMock(spec=PRResponse)
    mock_pr.ci_status = "SUCCESS"
    mock_github.get_pr.return_value = mock_pr

    # Mock comments
    mock_github.list_pr_comments.return_value = [
        {"id": 1, "author": {"login": "user1"}, "body": "Comment 1"}
    ]
    mock_github.list_pr_review_comments.return_value = [
        {"id": 2, "author": {"login": "user2"}, "body": "Review comment"}
    ]

    # Mock handoff service returns
    mock_handoff.record_ci_status.return_value = True
    mock_handoff.record_pr_comments.return_value = 2

    # Execute
    _fetch_and_record_external_events(
        pr_number=123,
        branch="test-branch",
        github_client=mock_github,
        handoff_svc=mock_handoff,
    )

    # Verify calls
    mock_github.get_pr.assert_called_once_with(123, None)
    mock_handoff.record_ci_status.assert_called_once_with(
        branch="test-branch",
        pr_number=123,
        status="SUCCESS",
    )
    mock_github.list_pr_comments.assert_called_once_with(123)
    mock_github.list_pr_review_comments.assert_called_once_with(123)
    mock_handoff.record_pr_comments.assert_called_once_with(
        branch="test-branch",
        pr_number=123,
        comments=[{"id": 1, "author": {"login": "user1"}, "body": "Comment 1"}],
        review_comments=[
            {"id": 2, "author": {"login": "user2"}, "body": "Review comment"}
        ],
    )


def test_fetch_and_record_external_events_graceful_failure() -> None:
    """Test that failures in fetching/recording are handled gracefully."""
    # Setup mocks
    mock_github = MagicMock()
    mock_handoff = MagicMock()

    # Mock PR fetch failure
    mock_github.get_pr.side_effect = Exception("API error")

    # Execute - should not raise
    _fetch_and_record_external_events(
        pr_number=123,
        branch="test-branch",
        github_client=mock_github,
        handoff_svc=mock_handoff,
    )

    # Verify partial progress before failure
    mock_github.get_pr.assert_called_once()


def test_fetch_and_record_external_events_comment_fetch_failure() -> None:
    """Test handling of comment fetch failures."""
    # Setup mocks
    mock_github = MagicMock()
    mock_handoff = MagicMock()

    # Mock PR with CI status
    mock_pr = MagicMock(spec=PRResponse)
    mock_pr.ci_status = "PENDING"
    mock_github.get_pr.return_value = mock_pr

    # Mock comment fetch failure
    mock_github.list_pr_comments.side_effect = Exception("API error")
    mock_github.list_pr_review_comments.return_value = []

    # Execute - should not raise
    _fetch_and_record_external_events(
        pr_number=123,
        branch="test-branch",
        github_client=mock_github,
        handoff_svc=mock_handoff,
    )

    # Verify CI status was recorded despite comment failure
    mock_handoff.record_ci_status.assert_called_once_with(
        branch="test-branch",
        pr_number=123,
        status="PENDING",
    )


def test_fetch_and_record_external_events_no_ci_status() -> None:
    """Test handling of PR without CI status."""
    # Setup mocks
    mock_github = MagicMock()
    mock_handoff = MagicMock()

    # Mock PR without CI status
    mock_pr = MagicMock(spec=PRResponse)
    mock_pr.ci_status = None
    mock_github.get_pr.return_value = mock_pr

    # Mock empty comments
    mock_github.list_pr_comments.return_value = []
    mock_github.list_pr_review_comments.return_value = []

    # Execute
    _fetch_and_record_external_events(
        pr_number=123,
        branch="test-branch",
        github_client=mock_github,
        handoff_svc=mock_handoff,
    )

    # Verify CI status was not recorded (None status)
    mock_handoff.record_ci_status.assert_not_called()
