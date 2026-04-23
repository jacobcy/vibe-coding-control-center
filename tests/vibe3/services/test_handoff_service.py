"""Tests for handoff ref validation and normalization."""

from pathlib import Path

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.services.handoff_service import HandoffService


class _StubGitClient:
    def __init__(self, worktree_root: Path, git_common_dir: Path, branch: str) -> None:
        self._worktree_root = worktree_root
        self._git_common_dir = git_common_dir
        self._branch = branch

    def get_current_branch(self) -> str:
        return self._branch

    def get_git_common_dir(self) -> str:
        return str(self._git_common_dir)

    def get_worktree_root(self) -> str:
        return str(self._worktree_root)

    def find_worktree_path_for_branch(self, branch: str) -> Path | None:
        if branch == self._branch:
            return self._worktree_root
        return None


def test_record_report_rejects_temp_log_paths(tmp_path: Path) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()
    log_path = worktree_root / "temp" / "logs" / "run.async.log"

    service = HandoffService(
        store=SQLiteClient(db_path=str(tmp_path / "handoff.db")),
        git_client=_StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    with pytest.raises(UserError, match="temp/logs"):
        service.record_report(str(log_path), actor="codex/gpt-5.4")


def test_record_report_rejects_shared_handoff_store_paths(tmp_path: Path) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    shared_ref = git_common / "vibe3" / "handoff" / "task-issue-304-a97faeda" / "run.md"
    shared_ref.parent.mkdir(parents=True)

    service = HandoffService(
        store=SQLiteClient(db_path=str(tmp_path / "handoff.db")),
        git_client=_StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    with pytest.raises(UserError, match="shared handoff store"):
        service.record_report(str(shared_ref), actor="codex/gpt-5.4")


def test_record_report_accepts_worktree_relative_canonical_doc(tmp_path: Path) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    report_path = worktree_root / "docs" / "reports" / "issue-304-report.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("ok", encoding="utf-8")

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=_StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    service.record_report("docs/reports/issue-304-report.md", actor="codex/gpt-5.4")

    flow_state = store.get_flow_state("task/issue-304")
    assert flow_state is not None
    assert flow_state["report_ref"] == "docs/reports/issue-304-report.md"
