"""Tests for issue role support helpers."""

from pathlib import Path
from unittest.mock import patch

from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    resolve_orchestra_repo_root,
)
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.orchestration import IssueInfo


def test_resolve_orchestra_repo_root_prefers_current_worktree() -> None:
    """Self-invocation should use the active worktree, not the shared repo root."""
    with patch("vibe3.execution.issue_role_support.GitClient") as mock_git:
        mock_git.return_value.get_worktree_root.return_value = (
            "/Users/jacobcy/src/vibe-center/wt-claude-v3"
        )
        mock_git.return_value.get_git_common_dir.return_value = (
            "/Users/jacobcy/src/vibe-center/main/.git"
        )

        root = resolve_orchestra_repo_root()

    assert root == Path("/Users/jacobcy/src/vibe-center/wt-claude-v3")


def test_build_issue_async_cli_request_uses_worktree_project_root() -> None:
    """Async issue self-invocation should target the current worktree project."""
    issue = IssueInfo(number=431, title="Test issue", labels=[])

    with patch(
        "vibe3.execution.issue_role_support.resolve_orchestra_repo_root",
        return_value=Path("/Users/jacobcy/src/vibe-center/wt-claude-v3"),
    ):
        request = build_issue_async_cli_request(
            role="manager",
            issue=issue,
            target_branch="task/issue-431",
            command_args=["internal", "manager", "431", "--no-async"],
            actor="agent:manager",
            execution_name="vibe3-manager-issue-431",
            refs={},
            worktree_requirement=WorktreeRequirement.PERMANENT,
        )

    assert request.cmd is not None
    assert request.cmd[3] == "/Users/jacobcy/src/vibe-center/wt-claude-v3"
    assert (
        request.cmd[6] == "/Users/jacobcy/src/vibe-center/wt-claude-v3/src/vibe3/cli.py"
    )
