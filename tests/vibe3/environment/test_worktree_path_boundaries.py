import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.environment.worktree import WorktreeManager
from vibe3.exceptions import SystemError
from vibe3.models.flow import FlowState
from vibe3.models.orchestra_config import OrchestraConfig


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def bare_repo_with_main_worktree(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    source.mkdir()
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.name", "Test")
    _git(source, "config", "user.email", "test@example.com")
    (source / "README.md").write_text("test\n")
    _git(source, "add", "README.md")
    _git(source, "commit", "-m", "init")

    bare_repo = tmp_path / "repo.git"
    subprocess.run(
        ["git", "clone", "--bare", str(source), str(bare_repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    main_worktree = bare_repo / ".worktrees" / "main"
    main_worktree.parent.mkdir()
    _git(bare_repo, "worktree", "add", str(main_worktree), "main")
    return bare_repo, main_worktree


def test_bare_repo_head_is_not_returned_as_checkout(bare_repo_with_main_worktree):
    repo_path, main_worktree = bare_repo_with_main_worktree
    manager = WorktreeManager(OrchestraConfig(), repo_path)

    cwd, missing = manager.resolve_manager_cwd(1, "main")

    assert missing is False
    assert cwd == main_worktree


def test_recorded_management_root_falls_back_to_registered_checkout(
    bare_repo_with_main_worktree,
):
    repo_path, main_worktree = bare_repo_with_main_worktree
    flow_service = MagicMock()
    flow_service.get_flow_state.return_value = FlowState(
        branch="main",
        flow_slug="issue-1",
        worktree_path=str(repo_path),
    )
    manager = WorktreeManager(OrchestraConfig(), repo_path, flow_service=flow_service)

    cwd, missing = manager.resolve_manager_cwd(1, "main")

    assert missing is False
    assert cwd == main_worktree


def test_no_worktree_mode_reuses_registered_checkout(bare_repo_with_main_worktree):
    repo_path, main_worktree = bare_repo_with_main_worktree
    manager = WorktreeManager(OrchestraConfig(), repo_path)

    context = manager.resolve_bootstrap_worktree_context(
        branch="main", issue_number=1, use_worktree=False
    )

    assert context.path == main_worktree


def test_no_worktree_mode_rejects_management_root_without_checkout(
    bare_repo_with_main_worktree,
):
    bare_repo, _ = bare_repo_with_main_worktree
    manager = WorktreeManager(OrchestraConfig(), bare_repo)

    with pytest.raises(SystemError, match="No registered worktree"):
        manager.resolve_bootstrap_worktree_context(
            branch="missing", issue_number=1, use_worktree=False
        )
