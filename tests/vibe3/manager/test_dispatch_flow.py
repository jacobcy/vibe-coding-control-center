"""Tests for manager role service request preparation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.manager import build_manager_request as build_manager_dispatch_request


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.READY,
        labels=["state/ready"],
    )


def make_config() -> OrchestraConfig:
    return OrchestraConfig(pid_file=Path(".git/vibe3/orchestra.pid"))


class TestManagerRoleServicePreparation:
    """Manager dispatch should be reduced to request preparation only."""

    def test_prepare_dispatch_request_returns_none_when_flow_missing_branch(self):
        issue = make_issue()

        with patch(
            "vibe3.domain.flow_manager.FlowManager.create_flow_for_issue",
            return_value={"branch": ""},
        ):
            assert (
                build_manager_dispatch_request(
                    make_config(),
                    issue,
                    repo_path=Path("/tmp/repo"),
                )
                is None
            )

    def test_prepare_dispatch_request_builds_self_invocation(self):
        issue = make_issue(number=102, title="Manager real dispatch")

        with patch(
            "vibe3.domain.flow_manager.FlowManager.create_flow_for_issue",
            return_value={"branch": "task/issue-102"},
        ):
            request = build_manager_dispatch_request(
                make_config(),
                issue,
                repo_path=Path("/tmp/repo"),
            )

        assert request is not None
        assert request.role == "manager"
        assert request.target_id == 102
        assert request.target_branch == "task/issue-102"
        assert request.cwd is None
        assert request.repo_path == str(Path("/tmp/repo").resolve())
        assert request.mode == "async"
        assert request.worktree_requirement == WorktreeRequirement.PERMANENT
        assert request.cmd is not None
        assert request.cmd[-3:] == [
            "manager",
            "102",
            "--no-async",
        ]
        assert "VIBE3_ASYNC_CHILD" in request.env
        assert request.refs["issue_title"] == "Manager real dispatch"


class TestTransientErrorLogging:
    """Manager should use warning for transient git errors, exception for others."""

    def test_transient_error_uses_warning(self):
        """Git ref lock conflict should be logged as warning, not exception."""
        issue = make_issue()

        with patch(
            "vibe3.domain.flow_manager.FlowManager.create_flow_for_issue",
            side_effect=RuntimeError(
                "Failed to create flow for issue #42: "
                "Git fetch origin failed: error: cannot lock ref "
                "'refs/remotes/origin/main': is at abc but expected def"
            ),
        ):
            with patch("vibe3.roles.manager.logger") as mock_logger:
                mock_bound = MagicMock()
                mock_logger.bind.return_value = mock_bound

                result = build_manager_dispatch_request(
                    make_config(), issue, repo_path=Path("/tmp/repo")
                )

        assert result is None
        mock_bound.warning.assert_called()
        mock_bound.exception.assert_not_called()

    def test_unexpected_error_uses_exception(self):
        """Unexpected errors should still log full traceback."""
        issue = make_issue()

        with patch(
            "vibe3.domain.flow_manager.FlowManager.create_flow_for_issue",
            side_effect=RuntimeError("Database connection refused"),
        ):
            with patch("vibe3.roles.manager.logger") as mock_logger:
                mock_bound = MagicMock()
                mock_logger.bind.return_value = mock_bound

                result = build_manager_dispatch_request(
                    make_config(), issue, repo_path=Path("/tmp/repo")
                )

        assert result is None
        mock_bound.exception.assert_called()
        mock_bound.warning.assert_not_called()

    def test_is_transient_git_error_patterns(self):
        """Unit test for classification logic."""
        from vibe3.exceptions import is_transient_git_error

        assert is_transient_git_error(
            "error: cannot lock ref 'refs/remotes/origin/main'"
        )
        assert is_transient_git_error("fatal: unable to update local ref")
        assert not is_transient_git_error("Database connection refused")
        assert not is_transient_git_error("Permission denied")
