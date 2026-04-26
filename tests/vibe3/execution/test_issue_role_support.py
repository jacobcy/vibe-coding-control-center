"""Tests for issue role support helpers."""

from pathlib import Path
from unittest.mock import patch

from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    resolve_async_cli_project_root,
    resolve_orchestra_repo_root,
)
from vibe3.execution.role_contracts import WorktreeRequirement
from vibe3.models.orchestration import IssueInfo

MAIN_REPO = Path("/test/repos/vibe-center/main")
WORKTREE_REPO = Path("/test/repos/vibe-center/main/.worktrees/wt-dev")


def test_resolve_orchestra_repo_root_prefers_git_common_dir_parent() -> None:
    """Normal orchestra operations should anchor to the main repository root."""
    with patch("vibe3.execution.issue_role_support.GitClient") as mock_git:
        mock_git.return_value.get_git_common_dir.return_value = f"{MAIN_REPO}/.git"

        root = resolve_orchestra_repo_root()

    assert root == MAIN_REPO


def test_resolve_async_cli_project_root_defaults_to_repo_root() -> None:
    """Without debug override, async child should run main-repo code."""
    root = resolve_async_cli_project_root(MAIN_REPO)
    assert root == MAIN_REPO


def test_resolve_async_cli_project_root_uses_debug_override(monkeypatch) -> None:
    """Debug mode should run async child from the current worktree code root."""
    monkeypatch.setenv("VIBE3_REPO_MODELS_ROOT", str(WORKTREE_REPO))

    root = resolve_async_cli_project_root(MAIN_REPO)

    assert root == WORKTREE_REPO


def test_build_issue_async_cli_request_uses_main_repo_by_default() -> None:
    """Async issue self-invocation should target main repo code in normal mode."""
    issue = IssueInfo(number=431, title="Test issue", labels=[])

    request = build_issue_async_cli_request(
        role="manager",
        issue=issue,
        target_branch="task/issue-431",
        command_args=["internal", "manager", "431", "--no-async"],
        actor="agent:manager",
        execution_name="vibe3-manager-issue-431",
        refs={},
        worktree_requirement=WorktreeRequirement.PERMANENT,
        repo_path=MAIN_REPO,
    )

    assert request.cmd is not None
    assert request.cmd[3] == str(MAIN_REPO)
    assert request.cmd[6] == str(MAIN_REPO / "src/vibe3/cli.py")
    assert request.repo_path == str(MAIN_REPO)


def test_build_issue_async_cli_request_uses_debug_code_root_override(
    monkeypatch,
) -> None:
    """Debug serve mode should only override the code root, not orchestration repo."""
    monkeypatch.setenv("VIBE3_REPO_MODELS_ROOT", str(WORKTREE_REPO))
    issue = IssueInfo(number=431, title="Test issue", labels=[])

    request = build_issue_async_cli_request(
        role="manager",
        issue=issue,
        target_branch="task/issue-431",
        command_args=["internal", "manager", "431", "--no-async"],
        actor="agent:manager",
        execution_name="vibe3-manager-issue-431",
        refs={},
        worktree_requirement=WorktreeRequirement.PERMANENT,
        repo_path=MAIN_REPO,
    )

    assert request.cmd is not None
    assert request.cmd[3] == str(WORKTREE_REPO)
    assert request.cmd[6] == str(WORKTREE_REPO / "src/vibe3/cli.py")
    # Worktree creation / shared state still anchor to main repo root.
    assert request.repo_path == str(MAIN_REPO)
