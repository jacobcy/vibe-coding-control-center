"""Tests for manager command/prompt helpers without ManagerExecutor shell."""

from pathlib import Path
from unittest.mock import patch

from tests.vibe3.conftest import CompletedProcess
from vibe3.environment.worktree_support import find_worktree_for_branch
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.manager import build_manager_command, render_manager_prompt


def make_issue(number: int = 42, title: str = "Test issue") -> IssueInfo:
    return IssueInfo(
        number=number,
        title=title,
        state=IssueState.CLAIMED,
        labels=["state/claimed"],
    )


class TestManagerCommandBuilding:
    def test_build_manager_command_formats_issue_prompt(self):
        issue = make_issue(number=88, title="Improve parser")

        rendered = render_manager_prompt(OrchestraConfig(), issue)
        cmd = build_manager_command(OrchestraConfig(), rendered.rendered_text)

        assert cmd[:6] == ["uv", "run", "python", "-m", "vibe3", "run"]
        assert "--async" in cmd
        assert "--worktree" not in cmd
        assert "Manage issue #88: Improve parser" in cmd[-1]
        assert "## Role" in cmd[-1]
        assert "状态控制器" in cmd[-1]
        assert "不是实现 agent" in cmd[-1]

    def test_find_worktree_for_branch_parses_porcelain_output(self) -> None:
        """Test parsing git worktree list porcelain output."""
        repo_path = Path("/tmp/repo")
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
            wt = find_worktree_for_branch(repo_path, "task/issue250-orchestra-manager")

        assert wt == Path("/tmp/wt-feature")
