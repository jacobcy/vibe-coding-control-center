"""Tests for issue role support helpers."""

from pathlib import Path
from unittest.mock import patch

from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
    resolve_async_cli_project_root,
    resolve_orchestra_repo_root,
)
from vibe3.models import IssueInfo, WorktreeRequirement

MAIN_REPO = Path("/test/repos/vibe-center/main")
WORKTREE_REPO = Path("/test/repos/vibe-center/main/.worktrees/wt-dev")
MODULE_REPO = Path(__file__).resolve().parents[3]


def test_resolve_orchestra_repo_root_prefers_git_common_dir_parent() -> None:
    """Normal orchestra operations should anchor to the main repository root."""
    from vibe3.utils.git_helpers import find_repo_root as _impl

    _impl.cache_clear()
    with patch(
        "vibe3.utils.git_helpers.get_git_common_dir", return_value=f"{MAIN_REPO}/.git"
    ):
        root = resolve_orchestra_repo_root()

    assert root == MAIN_REPO


def test_resolve_async_cli_project_root_defaults_to_repo_root() -> None:
    """Without override, async child should run the installed/source vibe3 code."""
    root = resolve_async_cli_project_root(MAIN_REPO)
    assert root == Path(__file__).resolve().parents[3]


def test_resolve_async_cli_project_root_uses_debug_override(monkeypatch) -> None:
    """Debug mode should run async child from the current worktree code root."""
    monkeypatch.setenv("VIBE3_ASYNC_CLI_PROJECT_ROOT", str(WORKTREE_REPO))

    root = resolve_async_cli_project_root(MAIN_REPO)

    assert root == WORKTREE_REPO


def test_resolve_async_cli_project_root_ignores_models_root_override(
    monkeypatch,
) -> None:
    """Cross-project models root must not hijack async child code resolution."""
    monkeypatch.setenv("VIBE3_REPO_MODELS_ROOT", "/tmp/external-repo")

    root = resolve_async_cli_project_root(MAIN_REPO)

    assert root == Path(__file__).resolve().parents[3]


def test_build_issue_async_cli_request_uses_main_repo_by_default() -> None:
    """Async issue self-invocation should target installed/source vibe3 code."""
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
    assert request.cmd[3] == str(MODULE_REPO)
    assert request.cmd[6] == str(MODULE_REPO / "src/vibe3/cli.py")
    assert request.repo_path == str(MAIN_REPO)


def test_build_issue_async_cli_request_uses_debug_code_root_override(
    monkeypatch,
) -> None:
    """Manual VIBE3_ASYNC_CLI_PROJECT_ROOT override for debugging purposes.

    Note: Serve command no longer sets this env var automatically (even in debug mode),
    as of PR #1662. This tests the manual override capability for advanced debugging
    scenarios where developers need to point to a specific vibe3 installation.

    The test verifies that when manually set, the override takes precedence over
    the default module-based resolution.
    """
    monkeypatch.setenv("VIBE3_ASYNC_CLI_PROJECT_ROOT", str(WORKTREE_REPO))
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


def test_build_issue_sync_prompt_request_with_session_does_not_pin_cwd() -> None:
    """Retry sync requests should still let coordinator resolve the worktree cwd."""
    issue = IssueInfo(number=431, title="Test issue", labels=[])

    request = build_issue_sync_prompt_request(
        role="manager",
        issue=issue,
        target_branch="task/issue-431",
        prompt="test prompt",
        task="test task",
        options=object(),
        actor="agent:manager",
        execution_name="vibe3-manager-issue-431",
        worktree_requirement=WorktreeRequirement.PERMANENT,
        session_id="session-431",
        repo_path=MAIN_REPO,
    )

    assert request.refs["session_id"] == "session-431"
    assert request.cwd is None
