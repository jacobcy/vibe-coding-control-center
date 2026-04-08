"""Tests for Orchestra ManagerExecutor - command building and utility functions."""

from pathlib import Path
from unittest.mock import patch

from tests.vibe3.conftest import CompletedProcess
from vibe3.manager.manager_executor import ManagerExecutor
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.config import OrchestraConfig


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


class TestManagerCommandBuilding:
    """Tests for command building."""

    def test_build_manager_command_formats_issue_prompt(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=88, title="Improve parser")

        cmd = manager.command_builder.build_manager_command(issue)

        assert cmd[:6] == ["uv", "run", "python", "-m", "vibe3", "run"]
        assert "--async" in cmd
        # --worktree flag removed after refactoring (worktree is self-managed)
        assert "--worktree" not in cmd
        assert "Manage issue #88: Improve parser" in cmd[-1]
        assert "## Role" in cmd[-1]
        assert "状态控制器" in cmd[-1]
        assert "不是实现 agent" in cmd[-1]

    def test_build_manager_command_can_disable_worktree_mode(self):
        config = OrchestraConfig()
        config.assignee_dispatch.use_worktree = False
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        issue = make_issue(number=89, title="Run in current flow")

        cmd = manager.command_builder.build_manager_command(issue)

        assert "--async" in cmd
        assert "--worktree" not in cmd
        assert "Manage issue #89: Run in current flow" in cmd[-1]


class TestManagerReviewDispatch:
    """Tests for PR review dispatch."""

    def test_prepare_pr_review_dispatch_returns_command_and_cwd(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            manager, "_resolve_review_cwd", return_value=Path("/tmp/wt-feature")
        ):
            # prepare_pr_review_dispatch was a test proxy, now we call components
            cmd = manager.command_builder.build_pr_review_command(42)
            cwd = manager._resolve_review_cwd_for_dispatch(42)

        assert cmd == ["uv", "run", "python", "-m", "vibe3", "review", "pr", "42"]
        assert cwd == Path("/tmp/wt-feature")

    def test_dispatch_pr_review_uses_resolved_worktree(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            manager, "_resolve_review_cwd", return_value=Path("/tmp/wt-feature")
        ):
            manager.status_service.get_active_flow_count = lambda: 0
            with patch(
                "subprocess.run",
                return_value=CompletedProcess(returncode=0),
            ) as mock_run:
                result = manager.dispatch_pr_review(42)

        assert result is True
        # ManagerExecutor calls run_command which calls subprocess.run
        cwd_calls = [c for c in mock_run.call_args_list if c[1].get("cwd") is not None]
        assert any(c[1]["cwd"] == Path("/tmp/wt-feature") for c in cwd_calls)

    def test_dispatch_pr_review_appends_async_flag_when_enabled(self):
        config = OrchestraConfig()
        config.pr_review_dispatch.async_mode = True
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(
            manager, "_resolve_review_cwd", return_value=Path("/tmp/wt-feature")
        ):
            manager.status_service.get_active_flow_count = lambda: 0
            with patch(
                "subprocess.run",
                return_value=CompletedProcess(returncode=0),
            ) as mock_run:
                result = manager.dispatch_pr_review(42)

        assert result is True
        async_calls = [c for c in mock_run.call_args_list if "--async" in c[0][0]]
        assert len(async_calls) > 0

    def test_prepare_pr_review_dispatch_can_force_wrapper_worktree(self):
        config = OrchestraConfig()
        config.pr_review_dispatch.use_worktree = True
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        with patch.object(manager, "_resolve_review_cwd") as mock_resolve:
            cmd = manager.command_builder.build_pr_review_command(42)
            cwd = manager._resolve_review_cwd_for_dispatch(42)

        mock_resolve.assert_not_called()
        # --worktree flag removed after refactoring (worktree is self-managed)
        assert "--worktree" not in cmd
        assert cwd == Path("/tmp/repo")


class TestManagerWorktreeResolution:
    """Tests for worktree and branch resolution utilities."""

    def test_find_worktree_for_branch_parses_porcelain_output(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))
        output = (
            "worktree /tmp/repo\n"
            "HEAD abcdef0\n"
            "branch refs/heads/main\n"
            "\n"
            "worktree /tmp/wt-feature\n"
            "HEAD 1234567\n"
            "branch refs/heads/task/issue250-orchestra-manager\n"
            "\n"
        )

        with patch(
            "subprocess.run",
            return_value=CompletedProcess(returncode=0, stdout=output),
        ):
            wt = manager.worktree_manager._find_worktree_for_branch(
                "task/issue250-orchestra-manager"
            )

        assert wt == Path("/tmp/wt-feature")

    def test_resolve_review_cwd_falls_back_to_repo_path(self):
        config = OrchestraConfig()
        manager = ManagerExecutor(config, repo_path=Path("/tmp/repo"))

        class _PR:
            head_branch = "task/missing"

        with patch(
            "vibe3.clients.github_client.GitHubClient.get_pr",
            return_value=_PR(),
        ):
            with patch.object(
                manager.worktree_manager,
                "_find_worktree_for_branch",
                return_value=None,
            ):
                cwd = manager._resolve_review_cwd(99)

        assert cwd == Path("/tmp/repo")
