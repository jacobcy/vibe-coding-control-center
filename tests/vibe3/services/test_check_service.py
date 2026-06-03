"""Tests for CheckService PR closed handling."""

from unittest.mock import MagicMock, patch

from vibe3.models.pr import PRState


def _make_check_pr_service():
    """Create a CheckPRService instance with mocked dependencies."""
    from vibe3.clients.git_client import GitClient
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.services.check_pr_service import CheckPRService
    from vibe3.services.flow_status_service import FlowStatusService

    store = MagicMock(spec=SQLiteClient)
    git_client = MagicMock(spec=GitClient)
    github_client = MagicMock(spec=GitHubClient)
    flow_status_service = MagicMock(spec=FlowStatusService)

    return CheckPRService(
        store=store,
        git_client=git_client,
        github_client=github_client,
        flow_status_service=flow_status_service,
    )


def test_handle_closed_pr_creates_bridge_issue() -> None:
    """When PR is closed (not merged), create bridge issue instead of rebuilding."""
    service = _make_check_pr_service()

    # Mock PR closed (not merged)
    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    # Mock issue links
    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]

    # Mock issue state (open)
    service.github_client.view_issue.return_value = {
        "state": "open",
        "title": "Original Issue",
        "body": "Original body",
        "labels": [{"name": "bug"}, {"name": "state/ready"}],
    }

    # Mock no existing bridge marker
    service.github_client.list_issue_comments.return_value = []

    # Mock bridge issue creation
    service.github_client.create_issue.return_value = 789

    # Mock successful comment and close operations
    service.github_client.add_comment.return_value = True
    service.github_client.close_issue_if_open.return_value = "closed"

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup = MagicMock()
        mock_cleanup_cls.return_value = mock_cleanup
        mock_cleanup.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": False,
            "flow_record": True,
        }

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

        # Verify bridge issue was created
        service.github_client.create_issue.assert_called_once()
        call_kwargs = service.github_client.create_issue.call_args.kwargs
        assert call_kwargs["title"] == "Follow-up: Original Issue"
        assert "state/ready" in call_kwargs["labels"]
        assert "bug" in call_kwargs["labels"]

        # Verify bridge marker was added
        service.github_client.add_comment.assert_called_once()
        marker_body = service.github_client.add_comment.call_args[0][1]
        assert "successor: #789" in marker_body
        assert "closed_pr: #123" in marker_body

        # Verify original issue was closed
        service.github_client.close_issue_if_open.assert_called_once()
        close_kwargs = service.github_client.close_issue_if_open.call_args.kwargs
        assert close_kwargs["issue_number"] == 456
        assert "#789" in close_kwargs["closing_comment"]

        # Verify flow was aborted and cleaned up
        service._flow_status_service.mark_flow_aborted.assert_called_once()

        assert handled is True
        assert len(issues) == 0


def test_handle_closed_pr_does_not_call_rebuild() -> None:
    """Verify that FlowRebuildUsecase is NOT called when PR closes."""
    service = _make_check_pr_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]
    service.github_client.view_issue.return_value = {
        "state": "open",
        "title": "Test Issue",
        "body": "Body",
        "labels": [],
    }
    service.github_client.list_issue_comments.return_value = []
    service.github_client.create_issue.return_value = 789
    service.github_client.add_comment.return_value = True
    service.github_client.close_issue_if_open.return_value = "closed"

    with (
        patch(
            "vibe3.services.check_pr_service.FlowRebuildUsecase", create=True
        ) as rebuild_cls,
        patch(
            "vibe3.services.flow_cleanup_service.FlowCleanupService"
        ) as mock_cleanup_cls,
    ):
        mock_cleanup = MagicMock()
        mock_cleanup_cls.return_value = mock_cleanup
        mock_cleanup.cleanup_flow_scene.return_value = {}

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

        # CRITICAL: Verify FlowRebuildUsecase was NOT instantiated
        rebuild_cls.assert_not_called()

        assert handled is True


def test_handle_closed_pr_with_closed_issue_marks_flow_aborted() -> None:
    """When PR closed and issue already closed, mark flow as aborted and cleanup."""
    service = _make_check_pr_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None  # Not merged

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]

    # Issue already closed on GitHub
    service.github_client.view_issue.return_value = {
        "state": "CLOSED",
    }

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup = MagicMock()
        mock_cleanup_cls.return_value = mock_cleanup
        # Mock cleanup result
        mock_cleanup.cleanup_flow_scene.return_value = {
            "worktree": True,
            "local_branch": True,
            "remote_branch": False,
            "flow_record": True,
        }

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

        # Verify flow was marked as aborted
        service._flow_status_service.mark_flow_aborted.assert_called_once()
        call_args = service._flow_status_service.mark_flow_aborted.call_args
        assert call_args[0][0] == "task/issue-456"
        assert "Issue #456 already closed" in call_args[0][1]
        assert "PR #123 closed without merge" in call_args[0][1]

        # Verify cleanup was called
        mock_cleanup.cleanup_flow_scene.assert_called_once_with(
            "task/issue-456",
            include_remote=True,
            keep_flow_record=False,
        )

        # Verify result includes warning about cleanup
        assert handled is True
        assert len(issues) == 0
        assert len(warnings) == 1
        assert "marked aborted" in warnings[0]
        assert "Issue #456 already closed" in warnings[0]


def test_handle_closed_pr_bridge_idempotency() -> None:
    """When bridge marker already exists, skip creation and just cleanup."""
    service = _make_check_pr_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]
    service.github_client.view_issue.return_value = {
        "state": "open",
        "title": "Original Issue",
        "body": "Body",
        "labels": [],
    }

    # Mock existing bridge marker
    service.github_client.list_issue_comments.return_value = [
        {
            "body": (
                "[flow] Bridge issue created\n\n"
                "successor: #789\n"
                "closed_pr: #123\n"
                "source_branch: task/issue-456\n"
                "status: unresolved_continues_in_successor"
            )
        }
    ]

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup = MagicMock()
        mock_cleanup_cls.return_value = mock_cleanup
        mock_cleanup.cleanup_flow_scene.return_value = {}
        service.github_client.close_issue_if_open.return_value = "closed"

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

        # Verify bridge issue was NOT created (idempotency)
        service.github_client.create_issue.assert_not_called()

        # Verify original issue is still closed before cleanup (retry-safe)
        service.github_client.close_issue_if_open.assert_called_once_with(
            issue_number=456,
            closing_comment=(
                "[flow] Closed after PR abandoned\n\n"
                "PR #123 was closed without merge, so this execution lineage "
                "is ended.\n"
                "The unresolved work continues in #789.\n"
            ),
        )

        # Verify flow was still aborted and cleaned up
        service._flow_status_service.mark_flow_aborted.assert_called_once()

        assert handled is True
        assert len(issues) == 0


def test_handle_closed_pr_existing_bridge_close_failure_does_not_cleanup() -> None:
    """When bridge marker exists but original close fails, preserve flow for retry."""
    service = _make_check_pr_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]
    service.github_client.view_issue.return_value = {
        "state": "open",
        "title": "Original Issue",
        "body": "Body",
        "labels": [],
    }
    service.github_client.list_issue_comments.return_value = [
        {
            "body": (
                "[flow] Bridge issue created\n\n"
                "successor: #789\n"
                "closed_pr: #123\n"
                "source_branch: task/issue-456\n"
                "status: unresolved_continues_in_successor"
            )
        }
    ]
    service.github_client.close_issue_if_open.return_value = "failed"

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup = MagicMock()
        mock_cleanup_cls.return_value = mock_cleanup

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

        service.github_client.create_issue.assert_not_called()
        service._flow_status_service.mark_flow_aborted.assert_not_called()
        mock_cleanup.cleanup_flow_scene.assert_not_called()

        assert handled is True
        assert len(issues) == 1
        assert "Bridge issue #789 already exists" in issues[0]
        assert "failed to close original issue #456" in issues[0]
        assert warnings == []


def test_handle_closed_pr_ignores_bridge_marker_for_prefixed_pr_number() -> None:
    """Bridge marker matching must not treat PR #1234 as PR #123."""
    service = _make_check_pr_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]
    service.github_client.view_issue.return_value = {
        "state": "open",
        "title": "Original Issue",
        "body": "Body",
        "labels": [],
    }
    service.github_client.list_issue_comments.return_value = [
        {"body": None},
        {
            "body": (
                "[flow] Bridge issue created\n\n"
                "successor: #789\n"
                "closed_pr: #1234\n"
                "source_branch: task/issue-456\n"
                "status: unresolved_continues_in_successor"
            )
        },
    ]
    service.github_client.create_issue.return_value = 790
    service.github_client.add_comment.return_value = True
    service.github_client.close_issue_if_open.return_value = "closed"

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup = MagicMock()
        mock_cleanup_cls.return_value = mock_cleanup
        mock_cleanup.cleanup_flow_scene.return_value = {}

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

        service.github_client.create_issue.assert_called_once()
        service.github_client.close_issue_if_open.assert_called_once()
        close_kwargs = service.github_client.close_issue_if_open.call_args.kwargs
        assert "#790" in close_kwargs["closing_comment"]

        assert handled is True
        assert issues == []
        assert len(warnings) == 1


def test_handle_closed_pr_when_view_issue_fails_does_not_cleanup() -> None:
    """When view_issue() fails (network/auth), do not cleanup flow, allow retry."""
    service = _make_check_pr_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]

    # Mock view_issue failure (returns non-dict)
    service.github_client.view_issue.return_value = "network_error"

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup = MagicMock()
        mock_cleanup_cls.return_value = mock_cleanup

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

        # Verify flow was NOT marked as aborted
        service._flow_status_service.mark_flow_aborted.assert_not_called()

        # Verify cleanup was NOT called (preserve flow for retry)
        mock_cleanup.cleanup_flow_scene.assert_not_called()

        # Verify error message returned (not empty)
        assert handled is True
        assert len(issues) == 1
        assert "Failed to fetch issue #456" in issues[0]
        assert "retry" in issues[0].lower()


def test_handle_closed_pr_when_close_original_fails_does_not_cleanup() -> None:
    """When close original issue fails, do not cleanup flow, preserve for retry."""
    service = _make_check_pr_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]

    service.github_client.view_issue.return_value = {
        "state": "open",
        "title": "Original Issue",
        "body": "Body",
        "labels": [],
    }
    service.github_client.list_issue_comments.return_value = []
    service.github_client.create_issue.return_value = 789

    # Mock marker addition failure
    service.github_client.add_comment.return_value = False

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup = MagicMock()
        mock_cleanup_cls.return_value = mock_cleanup

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

        # Verify flow was NOT marked as aborted
        service._flow_status_service.mark_flow_aborted.assert_not_called()

        # Verify cleanup was NOT called (preserve flow for retry)
        mock_cleanup.cleanup_flow_scene.assert_not_called()

        # Verify error message returned
        assert handled is True
        assert len(issues) == 1
        assert "Created bridge issue #789" in issues[0]
        assert "failed to add marker" in issues[0]


def test_handle_closed_pr_when_add_marker_fails_does_not_cleanup() -> None:
    """When add bridge marker fails, do not cleanup flow, preserve for retry."""
    service = _make_check_pr_service()

    mock_pr = MagicMock()
    mock_pr.number = 123
    mock_pr.state = PRState.CLOSED
    mock_pr.merged_at = None

    service.store.get_issue_links.return_value = [
        {"issue_role": "task", "issue_number": 456}
    ]

    service.github_client.view_issue.return_value = {
        "state": "open",
        "title": "Original Issue",
        "body": "Body",
        "labels": [],
    }
    service.github_client.list_issue_comments.return_value = []
    service.github_client.create_issue.return_value = 789
    service.github_client.add_comment.return_value = False

    with patch(
        "vibe3.services.flow_cleanup_service.FlowCleanupService"
    ) as mock_cleanup_cls:
        mock_cleanup = MagicMock()
        mock_cleanup_cls.return_value = mock_cleanup

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

        # Verify bridge issue was created
        service.github_client.create_issue.assert_called_once()

        # Verify marker addition was attempted
        service.github_client.add_comment.assert_called_once()

        # Verify flow was NOT marked as aborted (preserve for retry)
        service._flow_status_service.mark_flow_aborted.assert_not_called()

        # Verify cleanup was NOT called (preserve flow for retry)
        mock_cleanup.cleanup_flow_scene.assert_not_called()

        # Verify error message returned
        assert handled is True
        assert len(issues) == 1
        assert "Created bridge issue #789" in issues[0]
        assert "failed to add marker" in issues[0]
        assert "manually add marker comment" in issues[0]
