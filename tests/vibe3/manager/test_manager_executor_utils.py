"""Tests for Orchestra ManagerExecutor - command building and utility functions."""

from pathlib import Path
from unittest.mock import patch

from tests.vibe3.conftest import CompletedProcess
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
