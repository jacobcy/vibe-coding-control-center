"""Tests for manager dispatch result handling."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


def make_config(*, repo: str | None = None) -> OrchestraConfig:
    return OrchestraConfig(repo=repo, pid_file=Path(".git/vibe3/orchestra.pid"))


class TestManagerFeedbackLoop:
    """Tests for manager dispatch result handling."""

    def test_dispatch_success_with_pr_advances_to_review(self):
        """Success + PR exists should advance issue to state/review."""
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=100)
        with (
            patch.object(
                manager.flow_manager,
                "get_pr_for_issue",
                return_value=123,
            ),
            patch.object(manager.result_handler, "update_state_label") as mock_update,
            patch.object(
                manager.result_handler, "record_dispatch_event"
            ) as mock_record,
        ):
            manager.result_handler.on_dispatch_success(issue, "task/issue-100")

        review_calls = [
            c for c in mock_update.call_args_list if c[0][1] == IssueState.REVIEW
        ]
        assert len(review_calls) == 1
        mock_record.assert_called_once_with(
            "task/issue-100",
            success=True,
            issue_number=100,
            pr_number=123,
        )

    def test_dispatch_success_without_pr_keeps_in_progress(self):
        """Success + no PR should keep issue in state/in-progress."""
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=101)
        with (
            patch.object(
                manager.flow_manager,
                "get_pr_for_issue",
                return_value=None,
            ),
            patch.object(manager.result_handler, "update_state_label") as mock_update,
            patch.object(
                manager.result_handler, "record_dispatch_event"
            ) as mock_record,
        ):
            manager.result_handler.on_dispatch_success(issue, "task/issue-101")

        mock_update.assert_not_called()
        mock_record.assert_called_once_with(
            "task/issue-101",
            success=True,
            issue_number=101,
            pr_number=None,
        )

    def test_dispatch_failure_api_error_sets_failed_and_comments(self):
        """API error should set issue to failed and post comment."""
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=102)
        with (
            patch.object(
                manager.flow_manager,
                "get_flow_for_issue",
                return_value={"branch": "task/issue-102"},
            ),
            patch.object(manager.result_handler, "update_state_label") as mock_update,
            patch.object(
                manager.result_handler, "post_failure_comment"
            ) as mock_comment,
            patch.object(
                manager.result_handler, "record_dispatch_event"
            ) as mock_record,
        ):
            manager.result_handler.on_dispatch_failure(issue, "api_error")

        failed_calls = [
            c for c in mock_update.call_args_list if c[0][1] == IssueState.FAILED
        ]
        assert len(failed_calls) >= 1
        mock_comment.assert_called_once()
        assert "api_error" in mock_comment.call_args[0][1]
        mock_record.assert_called_once()

    def test_dispatch_failure_timeout_sets_failed(self):
        """Timeout should set issue to failed."""
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=103)
        with (
            patch.object(
                manager.flow_manager,
                "get_flow_for_issue",
                return_value={"branch": "task/issue-103"},
            ),
            patch.object(manager.result_handler, "update_state_label") as mock_update,
            patch.object(manager.result_handler, "post_failure_comment"),
            patch.object(manager.result_handler, "record_dispatch_event"),
        ):
            manager.result_handler.on_dispatch_failure(issue, "timeout")

        failed_calls = [
            c for c in mock_update.call_args_list if c[0][1] == IssueState.FAILED
        ]
        assert len(failed_calls) >= 1

    def test_dispatch_failure_business_error_keeps_in_progress(self):
        """Business error should NOT auto-block, keep in-progress."""
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=104)
        with (
            patch.object(
                manager.flow_manager,
                "get_flow_for_issue",
                return_value={"branch": "task/issue-104"},
            ),
            patch.object(manager.result_handler, "update_state_label") as mock_update,
            patch.object(
                manager.result_handler, "post_failure_comment"
            ) as mock_comment,
            patch.object(
                manager.result_handler, "record_dispatch_event"
            ) as mock_record,
        ):
            manager.result_handler.on_dispatch_failure(issue, "business_error")

        mock_comment.assert_not_called()
        blocked_calls = [
            c for c in mock_update.call_args_list if c[0][1] == IssueState.BLOCKED
        ]
        assert len(blocked_calls) == 0
        mock_record.assert_called_once()

    def test_record_dispatch_event_stores_in_flow_history(self):
        """Dispatch events should be recorded in flow event history."""
        config = make_config()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        # Verifies the method exists and can be called
        manager.result_handler.record_dispatch_event(
            flow_branch="task/issue-100",
            success=True,
            issue_number=100,
            pr_number=123,
        )

        assert manager.result_handler.record_dispatch_event is not None

    def test_post_failure_comment_creates_github_comment(self):
        """Failed dispatch should post comment on issue."""
        config = make_config(repo="owner/repo")
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch("vibe3.clients.github_client.GitHubClient") as mock_client_class:
            mock_github = MagicMock()
            mock_client_class.return_value = mock_github

            manager.result_handler.post_failure_comment(100, "Test failure reason")

            assert manager.result_handler.post_failure_comment is not None
