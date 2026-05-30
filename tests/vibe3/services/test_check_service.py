"""Tests for CheckService PR closed handling."""

from unittest.mock import MagicMock, patch

from vibe3.models.pr import PRState


def _make_check_pr_service():
    """Create a CheckPRService instance with mocked dependencies."""
    from vibe3.clients import GitClient, GitHubClient, SQLiteClient
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


def test_handle_closed_pr_resets_issue_to_ready() -> None:
    """When PR is closed (not merged), issue should be reset to READY."""
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
    }

    with (
        patch(
            "vibe3.services.task_resume_operations.TaskResumeOperations"
        ) as mock_resume_ops_cls,
        patch(
            "vibe3.services.flow_orchestrator_service.FlowOrchestratorService"
        ) as mock_orchestrator_cls,
        patch("vibe3.services.handoff_service.HandoffService") as mock_handoff_cls,
        patch("vibe3.services.issue_context_loader.load_issue_info") as mock_load_issue,
    ):
        mock_resume_ops = MagicMock()
        mock_resume_ops_cls.return_value = mock_resume_ops

        mock_orchestrator = MagicMock()
        mock_orchestrator_cls.return_value = mock_orchestrator

        mock_handoff = MagicMock()
        mock_handoff_cls.return_value = mock_handoff

        # Mock issue info
        from vibe3.models.orchestration import IssueInfo

        mock_issue_info = IssueInfo(number=456, title="Test Issue", labels=[])
        mock_load_issue.return_value = mock_issue_info

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

        # Verify reset_issue_to_ready was called
        mock_resume_ops.reset_issue_to_ready.assert_called_once()
        call_kwargs = mock_resume_ops.reset_issue_to_ready.call_args[1]
        assert call_kwargs["issue_number"] == 456
        assert call_kwargs["resume_kind"] == "pr_closed"

        # Verify flow rebuild was attempted
        mock_orchestrator.bootstrap_issue_flow.assert_called_once()

        # Verify handoff milestone was recorded
        mock_handoff.append_current_handoff.assert_called_once()

        # Verify result is valid and handled
        assert handled is True
        assert len(issues) == 0


def test_handle_closed_pr_reports_reset_failure() -> None:
    """When reset fails, check should report the closed PR cleanup as invalid."""
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
    }

    with patch(
        "vibe3.services.task_resume_operations.TaskResumeOperations"
    ) as mock_resume_ops_cls:
        mock_resume_ops = MagicMock()
        mock_resume_ops.reset_issue_to_ready.side_effect = RuntimeError(
            "scene cleanup failed"
        )
        mock_resume_ops_cls.return_value = mock_resume_ops

        handled, issues, warnings = service.handle_closed_pr("task/issue-456", mock_pr)

    assert handled is True
    assert issues == [
        "Failed to reset issue #456 after PR #123 closed: scene cleanup failed"
    ]


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
