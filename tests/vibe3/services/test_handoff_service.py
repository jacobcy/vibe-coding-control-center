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


def test_get_handoff_events_excludes_non_handoff_runtime_events(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=_StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "tmux_manager_started", "orchestra:manager")
    store.add_event(
        branch, "codeagent_manager_started", "gemini/gemini-3-flash-preview"
    )
    store.add_event(branch, "handoff_plan", "codex/gpt-5.4", detail="plan ready")
    store.add_event(branch, "audit_recorded", "codex/gpt-5.4", detail="auto audit")
    store.add_event(branch, "state_transitioned", "codex/gpt-5.4", detail="advanced")

    events = service.get_handoff_events(branch)

    assert [event.event_type for event in events] == [
        "audit_recorded",
        "handoff_plan",
    ]


def test_get_handoff_events_applies_limit_after_handoff_filter(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=_StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "handoff_plan", "codex/gpt-5.4", detail="oldest handoff")
    store.add_event(branch, "state_transitioned", "codex/gpt-5.4", detail="noise")
    store.add_event(branch, "handoff_report", "codex/gpt-5.4", detail="newest handoff")

    events = service.get_handoff_events(branch, limit=1)

    assert len(events) == 1
    assert events[0].event_type == "handoff_report"


def test_get_handoff_events_includes_both_active_and_passive_events(
    tmp_path: Path,
) -> None:
    """Both active (handoff_*) and passive (*_recorded) events should be shown.

    Passive events serve as fallback records when active writes fail,
    so they should not be filtered out even when active events exist.
    """
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=_StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "plan_recorded", "codex/gpt-5.4", detail="auto plan")
    store.add_event(branch, "handoff_plan", "codex/gpt-5.4", detail="plan ready")

    events = service.get_handoff_events(branch)

    # Both events should be present (order: newest first)
    assert [event.event_type for event in events] == ["handoff_plan", "plan_recorded"]


def test_get_handoff_events_keeps_recorded_run_when_no_active_handoff(
    tmp_path: Path,
) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=_StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "run_recorded", "codex/gpt-5.4", detail="auto run")

    events = service.get_handoff_events(branch)

    assert [event.event_type for event in events] == ["run_recorded"]


def test_get_success_handoff_events_filters_passive_and_manager_events(
    tmp_path: Path,
) -> None:
    """Verify get_success_handoff_events excludes *_recorded and handoff_indicate."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=_StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    # Add a mix of event types
    store.add_event(branch, "plan_recorded", "codex/gpt-5.4", detail="auto plan")
    store.add_event(branch, "handoff_plan", "codex/gpt-5.4", detail="plan ready")
    store.add_event(branch, "handoff_indicate", "manager", detail="manager indicate")
    store.add_event(branch, "handoff_audit", "codex/gpt-5.4", detail="audit ready")
    store.add_event(branch, "audit_recorded", "codex/gpt-5.4", detail="auto audit")

    success_events = service.get_success_handoff_events(branch)
    event_types = {e.event_type for e in success_events}

    # Only success handoff events should be present
    assert "plan_recorded" not in event_types
    assert "audit_recorded" not in event_types
    assert "handoff_indicate" not in event_types
    assert "handoff_plan" in event_types
    assert "handoff_audit" in event_types


def test_get_success_handoff_events_applies_limit(tmp_path: Path) -> None:
    """Verify limit is applied after success filter."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=_StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "handoff_plan", "codex/gpt-5.4", detail="oldest")
    store.add_event(branch, "handoff_report", "codex/gpt-5.4", detail="middle")
    store.add_event(branch, "handoff_audit", "codex/gpt-5.4", detail="newest")

    events = service.get_success_handoff_events(branch, limit=2)

    assert len(events) == 2
    # Should return newest first (audit, report)
    assert events[0].event_type == "handoff_audit"
    assert events[1].event_type == "handoff_report"
