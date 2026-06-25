"""Integration tests for handoff init with issue context.

Tests the issue context fetching logic inside the handoff init command,
covering normal flow, error handling, and quiet mode.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app
from vibe3.services.task import TaskCommentSummary

runner = CliRunner()


class TestHandoffInitIssueContext:
    """Integration tests for handoff init issue context fetching."""

    @patch("vibe3.services.pr.PRService")
    @patch("vibe3.services.task.TaskShowService")
    @patch("vibe3.services.issue.IssueFlowService")
    @patch("vibe3.services.flow.FlowService")
    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_init_fetches_issue_context(
        self,
        mock_handoff_cls,
        mock_flow_cls,
        mock_issue_flow_cls,
        mock_task_show_cls,
        mock_pr_cls,
    ):
        """Normal flow: issue context is fetched and appended to handoff."""
        # FlowService mock
        mock_flow_cls.return_value = MagicMock()

        # IssueFlowService: resolve issue number
        mock_issue_flow = MagicMock()
        mock_issue_flow.resolve_task_issue_number.return_value = 3148
        mock_issue_flow_cls.return_value = mock_issue_flow

        # TaskShowService: return issue data with human comment
        mock_issue_data = {
            "title": "Test issue",
            "state": "open",
            "number": 3148,
            "comments": [
                {
                    "author": {"login": "human-user"},
                    "body": "Please implement this feature",
                    "createdAt": "2024-01-01T00:00:00Z",
                },
            ],
        }
        mock_task_show = MagicMock()
        mock_task_show.fetch_issue_with_comments.return_value = mock_issue_data
        mock_task_show.build_comment_summary.return_value = TaskCommentSummary(
            author="human-user",
            body="Please implement this feature",
        )
        mock_task_show_cls.return_value = mock_task_show

        # PRService: return PR status
        mock_pr = MagicMock()
        mock_pr_response = MagicMock()
        mock_pr_response.number = 42
        mock_pr_response.ci_status = "success"
        mock_pr.get_branch_pr_status.return_value = mock_pr_response
        mock_pr_cls.return_value = mock_pr

        # HandoffService
        mock_handoff = MagicMock()
        mock_handoff.storage.ensure_current_handoff.return_value = "/path/to/current.md"
        mock_handoff_cls.return_value = mock_handoff

        result = runner.invoke(app, ["handoff", "init", "--branch", "task/test-branch"])

        assert result.exit_code == 0
        # Verify issue context was appended (summary + human comment + CI status)
        assert mock_handoff.append_current_handoff.call_count >= 1

    @patch("vibe3.services.task.TaskShowService")
    @patch("vibe3.services.issue.IssueFlowService")
    @patch("vibe3.services.flow.FlowService")
    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_init_handles_github_api_failure(
        self,
        mock_handoff_cls,
        mock_flow_cls,
        mock_issue_flow_cls,
        mock_task_show_cls,
    ):
        """GitHub API failure: init handles gracefully, no crash."""
        mock_flow_cls.return_value = MagicMock()

        mock_issue_flow = MagicMock()
        mock_issue_flow.resolve_task_issue_number.return_value = 3148
        mock_issue_flow_cls.return_value = mock_issue_flow

        mock_task_show = MagicMock()
        mock_task_show.fetch_issue_with_comments.side_effect = Exception(
            "GitHub API error"
        )
        mock_task_show_cls.return_value = mock_task_show

        mock_handoff = MagicMock()
        mock_handoff.storage.ensure_current_handoff.return_value = "/path/to/current.md"
        mock_handoff_cls.return_value = mock_handoff

        result = runner.invoke(app, ["handoff", "init", "--branch", "task/test-branch"])

        # Non-critical failure: should still succeed
        assert result.exit_code == 0

    @patch("vibe3.services.task.TaskShowService")
    @patch("vibe3.services.issue.IssueFlowService")
    @patch("vibe3.services.flow.FlowService")
    @patch("vibe3.commands.handoff_write.HandoffService")
    def test_handoff_init_handles_task_show_service_failure(
        self,
        mock_handoff_cls,
        mock_flow_cls,
        mock_issue_flow_cls,
        mock_task_show_cls,
    ):
        """TaskShowService init failure: init handles gracefully, no crash."""
        mock_flow_cls.return_value = MagicMock()

        mock_issue_flow = MagicMock()
        mock_issue_flow.resolve_task_issue_number.return_value = 3148
        mock_issue_flow_cls.return_value = mock_issue_flow

        # TaskShowService constructor raises
        mock_task_show_cls.side_effect = Exception("TaskShowService init failed")

        mock_handoff = MagicMock()
        mock_handoff.storage.ensure_current_handoff.return_value = "/path/to/current.md"
        mock_handoff_cls.return_value = mock_handoff

        result = runner.invoke(app, ["handoff", "init", "--branch", "task/test-branch"])

        # Non-critical failure: should still succeed
        assert result.exit_code == 0

    def test_handoff_init_quiet_mode(self):
        """Quiet mode (_quiet=True) suppresses handoff ready output."""
        from vibe3.commands.handoff_write import init

        with (
            patch("vibe3.services.flow.service.FlowService"),
            patch("vibe3.commands.handoff_write.HandoffService") as mock_hs,
        ):
            mock_hs.return_value.storage.ensure_current_handoff.return_value = (
                "/path/to/md"
            )

            # Should complete without error
            init(force=False, branch="task/test-branch", trace=False, _quiet=True)
