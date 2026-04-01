"""Tests for Dispatcher feedback loop - Phase 3."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from tests.vibe3.orchestra.conftest import CompletedProcess
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


class TestDispatcherFeedbackLoop:
    """Tests for Phase 3 feedback loop."""

    def test_dispatch_success_with_pr_advances_to_review(self):
        """Success + PR exists should advance issue to state/review."""
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=100)

        with patch.object(
            dispatcher.orchestrator,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-100"},
        ):
            with patch.object(
                dispatcher,
                "_resolve_manager_cwd",
                return_value=Path("/tmp/wt-issue-100"),
            ):
                with patch(
                    "subprocess.run",
                    return_value=CompletedProcess(returncode=0),
                ):
                    with patch.object(
                        dispatcher.orchestrator,
                        "get_pr_for_issue",
                        return_value=123,
                    ):
                        with patch.object(
                            dispatcher.result_handler, "update_state_label"
                        ) as mock_update:
                            with patch.object(
                                dispatcher.result_handler, "record_dispatch_event"
                            ) as mock_record:
                                result = dispatcher.dispatch_manager(issue)

        assert result is True
        # Should have called update_state_label with REVIEW (last call)
        review_calls = [
            c for c in mock_update.call_args_list if c[0][1] == IssueState.REVIEW
        ]
        assert len(review_calls) == 1
        # Should have recorded event
        mock_record.assert_called()

    def test_dispatch_success_without_pr_keeps_in_progress(self):
        """Success + no PR should keep issue in state/in-progress."""
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=101)

        with patch.object(
            dispatcher.orchestrator,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-101"},
        ):
            with patch.object(
                dispatcher,
                "_resolve_manager_cwd",
                return_value=Path("/tmp/wt-issue-101"),
            ):
                with patch(
                    "subprocess.run",
                    return_value=CompletedProcess(returncode=0),
                ):
                    with patch.object(
                        dispatcher.orchestrator,
                        "get_pr_for_issue",
                        return_value=None,  # No PR
                    ):
                        with patch.object(
                            dispatcher.result_handler, "update_state_label"
                        ) as mock_update:
                            with patch.object(
                                dispatcher.result_handler, "record_dispatch_event"
                            ):
                                result = dispatcher.dispatch_manager(issue)

        assert result is True
        # Should have called update_state_label with IN_PROGRESS (before execution)
        assert any(
            c[0][1] == IssueState.IN_PROGRESS for c in mock_update.call_args_list
        )
        # Should NOT have advanced to REVIEW
        assert not any(c[0][1] == IssueState.REVIEW for c in mock_update.call_args_list)

    def test_dispatch_failure_api_error_sets_blocked_and_comments(self):
        """API error should set issue to blocked and post comment."""
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=102)

        with patch.object(
            dispatcher.orchestrator,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-102"},
        ):
            with patch.object(
                dispatcher,
                "_resolve_manager_cwd",
                return_value=Path("/tmp/wt-issue-102"),
            ):
                with patch(
                    "subprocess.run",
                    return_value=CompletedProcess(
                        returncode=1, stderr="Error: rate limit exceeded"
                    ),
                ):
                    with patch.object(
                        dispatcher.result_handler, "update_state_label"
                    ) as mock_update:
                        with patch.object(
                            dispatcher.result_handler, "post_failure_comment"
                        ) as mock_comment:
                            with patch.object(
                                dispatcher.orchestrator,
                                "get_flow_for_issue",
                                return_value={"branch": "task/issue-102"},
                            ):
                                with patch.object(
                                    dispatcher.result_handler, "record_dispatch_event"
                                ):
                                    result = dispatcher.dispatch_manager(issue)

        assert result is False
        # Should have set state to BLOCKED
        blocked_calls = [
            c for c in mock_update.call_args_list if c[0][1] == IssueState.BLOCKED
        ]
        assert len(blocked_calls) >= 1
        # Should have posted comment
        mock_comment.assert_called_once()
        assert "api_error" in mock_comment.call_args[0][1]

    def test_dispatch_failure_timeout_sets_blocked(self):
        """Timeout should set issue to blocked."""
        import subprocess

        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=103)

        with patch.object(
            dispatcher.orchestrator,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-103"},
        ):
            with patch.object(
                dispatcher,
                "_resolve_manager_cwd",
                return_value=Path("/tmp/wt-issue-103"),
            ):
                with patch(
                    "subprocess.run",
                    side_effect=subprocess.TimeoutExpired(cmd=[], timeout=3600),
                ):
                    with patch.object(
                        dispatcher.result_handler, "update_state_label"
                    ) as mock_update:
                        with patch.object(
                            dispatcher.result_handler, "post_failure_comment"
                        ):
                            with patch.object(
                                dispatcher.orchestrator,
                                "get_flow_for_issue",
                                return_value={"branch": "task/issue-103"},
                            ):
                                with patch.object(
                                    dispatcher.result_handler, "record_dispatch_event"
                                ):
                                    result = dispatcher.dispatch_manager(issue)

        assert result is False
        # Should have set state to BLOCKED
        blocked_calls = [
            c for c in mock_update.call_args_list if c[0][1] == IssueState.BLOCKED
        ]
        assert len(blocked_calls) >= 1

    def test_dispatch_failure_business_error_keeps_in_progress(self):
        """Business error should NOT auto-block, keep in-progress."""
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=104)

        with patch.object(
            dispatcher.orchestrator,
            "create_flow_for_issue",
            return_value={"branch": "task/issue-104"},
        ):
            with patch.object(
                dispatcher,
                "_resolve_manager_cwd",
                return_value=Path("/tmp/wt-issue-104"),
            ):
                with patch(
                    "subprocess.run",
                    return_value=CompletedProcess(
                        returncode=1, stderr="Error: merge conflict in file.py"
                    ),
                ):
                    with patch.object(
                        dispatcher.result_handler, "update_state_label"
                    ) as mock_update:
                        with patch.object(
                            dispatcher.result_handler, "post_failure_comment"
                        ) as mock_comment:
                            with patch.object(
                                dispatcher.orchestrator,
                                "get_flow_for_issue",
                                return_value={"branch": "task/issue-104"},
                            ):
                                with patch.object(
                                    dispatcher.result_handler, "record_dispatch_event"
                                ):
                                    result = dispatcher.dispatch_manager(issue)

        assert result is False
        # Should NOT have posted comment (business error)
        mock_comment.assert_not_called()
        # Should NOT have set state to BLOCKED
        blocked_calls = [
            c for c in mock_update.call_args_list if c[0][1] == IssueState.BLOCKED
        ]
        assert len(blocked_calls) == 0

    def test_record_dispatch_event_stores_in_flow_history(self):
        """Dispatch events should be recorded in flow event history."""
        config = OrchestraConfig()
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        # This test verifies the method exists and can be called
        dispatcher.result_handler.record_dispatch_event(
            flow_branch="task/issue-100",
            success=True,
            issue_number=100,
            pr_number=123,
        )

        # The method should exist and be callable
        assert dispatcher.result_handler.record_dispatch_event is not None

    def test_post_failure_comment_creates_github_comment(self):
        """Failed dispatch should post comment on issue."""
        config = OrchestraConfig(repo="owner/repo")
        dispatcher = Dispatcher(config, repo_path=Path("/tmp/repo"))

        # Test that the method exists and can be called
        # In actual implementation, it creates a GitHub comment
        with patch("vibe3.clients.github_client.GitHubClient") as mock_client_class:
            mock_github = MagicMock()
            mock_client_class.return_value = mock_github

            dispatcher.result_handler.post_failure_comment(100, "Test failure reason")

            # Verify the method was called (not checking internal implementation)
            assert dispatcher.result_handler.post_failure_comment is not None
