"""Tests for handoff ref validation and normalization."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import UserError
from vibe3.services.handoff import HandoffService


class StubGitClient:
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
        return self._worktree_root if branch == self._branch else None


def test_record_report_rejects_temp_log_paths(tmp_path: Path) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()
    log_path = worktree_root / "temp" / "logs" / "run.async.log"

    service = HandoffService(
        store=SQLiteClient(db_path=str(tmp_path / "handoff.db")),
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
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
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
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
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    service.record_report("docs/reports/issue-304-report.md", actor="codex/gpt-5.4")

    flow_state = store.get_flow_state("task/issue-304")
    assert flow_state is not None
    assert flow_state["report_ref"] == "docs/reports/issue-304-report.md"


def test_record_indicate_writes_indicate_ref(tmp_path: Path) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    indicate_path = worktree_root / "docs" / "indicate.md"
    indicate_path.parent.mkdir(parents=True)
    indicate_path.write_text("manager direction", encoding="utf-8")

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    service.record_indicate("docs/indicate.md", actor="codex/gpt-5.4")

    flow_state = store.get_flow_state("task/issue-304")
    assert flow_state is not None
    assert flow_state["indicate_ref"] == "docs/indicate.md"
    assert flow_state["manager_actor"] == "codex/gpt-5.4"


def test_record_spec_writes_canonical_spec_ref(tmp_path: Path) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    spec_path = (
        worktree_root / ".specify" / "specs" / "012-spec-handoff-bridge" / "spec.md"
    )
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("# Spec\n", encoding="utf-8")

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-3310"),
    )

    service.record_spec(
        ".specify/specs/012-spec-handoff-bridge/spec.md", actor="planner"
    )

    flow_state = store.get_flow_state("task/issue-3310")
    assert flow_state is not None
    assert flow_state["spec_ref"] == ".specify/specs/012-spec-handoff-bridge/spec.md"
    events = service.get_handoff_events("task/issue-3310")
    assert any(e.event_type == "handoff_spec" for e in events)


def _make_spec_service(tmp_path: Path) -> tuple[SQLiteClient, HandoffService, Path]:
    """Fixture: worktree with a canonical spec file present."""
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    spec_path = (
        worktree_root / ".specify" / "specs" / "012-spec-handoff-bridge" / "spec.md"
    )
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text("# Spec\n", encoding="utf-8")
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-3310"),
    )
    return store, service, worktree_root


@pytest.mark.parametrize(
    "bad_ref",
    [
        "#3310",  # legacy issue-id (write-strict rejection, T013)
        "3310",  # bare issue number
        "https://example.com/spec.md",  # URL
        "/abs/path/spec.md",  # absolute path
        "docs/spec.md",  # non-canonical location
        ".specify/specs/012-spec-handoff-bridge/spec.txt",  # wrong filename
        ".specify/specs/spec.md",  # missing NNN-slug segment
    ],
)
def test_record_spec_rejects_non_canonical_forms(tmp_path: Path, bad_ref: str) -> None:
    _, service, _ = _make_spec_service(tmp_path)

    with pytest.raises(UserError, match="canonical repository-relative path"):
        service.record_spec(bad_ref, actor="planner")


def test_record_spec_rejects_missing_file(tmp_path: Path) -> None:
    """Canonical shape but file does not exist → rejected."""
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-3310"),
    )

    with pytest.raises(UserError, match="existing regular file"):
        service.record_spec(".specify/specs/099-missing/spec.md", actor="planner")


def test_record_spec_rejects_directory_at_spec_md(tmp_path: Path) -> None:
    """spec.md resolves to a directory, not a regular file → rejected."""
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    dir_at_spec = worktree_root / ".specify" / "specs" / "012-foo" / "spec.md"
    dir_at_spec.mkdir(parents=True)
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-3310"),
    )

    with pytest.raises(UserError, match="existing regular file"):
        service.record_spec(".specify/specs/012-foo/spec.md", actor="planner")


def test_record_spec_no_partial_mutation_on_rejection(tmp_path: Path) -> None:
    """Failed validation must not write spec_ref or emit an event (FR-007)."""
    store, service, _ = _make_spec_service(tmp_path)

    with pytest.raises(UserError):
        service.record_spec("#3310", actor="planner")

    # Validation runs before _record_ref, so neither a flow_state row nor an
    # event is produced. Accept both "no row" and "row without spec_ref".
    flow_state = store.get_flow_state("task/issue-3310")
    if flow_state is not None:
        assert flow_state.get("spec_ref") in (None, "")
    events = service.get_handoff_events("task/issue-3310")
    assert not any(e.event_type == "handoff_spec" for e in events)


def test_record_spec_idempotent_rerecord(tmp_path: Path) -> None:
    """Re-recording the same canonical spec_ref is safe (FR-009)."""
    store, service, _ = _make_spec_service(tmp_path)
    canonical = ".specify/specs/012-spec-handoff-bridge/spec.md"

    service.record_spec(canonical, actor="planner")
    service.record_spec(canonical, actor="planner")

    flow_state = store.get_flow_state("task/issue-3310")
    assert flow_state is not None
    assert flow_state["spec_ref"] == canonical


def test_record_ref_event_refs_use_database_ref_field(tmp_path: Path) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    plan_path = worktree_root / "docs" / "plans" / "test.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("plan content", encoding="utf-8")

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )
    handoff_file = git_common / "vibe3" / "handoff" / "task-issue-304" / "current.md"
    service.storage.ensure_current_handoff = MagicMock(return_value=handoff_file)
    service.storage.append_current_handoff = MagicMock(return_value=handoff_file)
    service.storage.normalize_ref_value = MagicMock(return_value="docs/plans/test.md")

    service._record_ref("plan", "docs/plans/test.md", actor="planner")

    events = service.get_handoff_events("task/issue-304")
    assert events[0].refs == {"plan_ref": "docs/plans/test.md"}


def test_record_passive_artifact_event_refs_use_database_ref_field(
    tmp_path: Path,
) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    artifact_path = service.record_passive_artifact(
        kind="run",
        content="### Modified Files\n- src/vibe3/example.py\n",
        actor="executor",
    )

    assert artifact_path is not None
    events = store.get_events("task/issue-304", event_type="report_recorded")
    assert events[0]["refs"]["report_ref"].startswith("@task-issue-304-")
    assert "/report-" in events[0]["refs"]["report_ref"]
    assert "ref" not in events[0]["refs"]


def test_record_ref_rejects_unknown_active_kind(tmp_path: Path) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()

    service = HandoffService(
        store=SQLiteClient(db_path=str(tmp_path / "handoff.db")),
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    with pytest.raises(UserError, match="Unsupported handoff kind: mystery"):
        service._record_ref("mystery", "docs/unknown.md", actor="codex/gpt-5.4")


def test_record_ref_rejects_legacy_positional_shape(tmp_path: Path) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()

    service = HandoffService(
        store=SQLiteClient(db_path=str(tmp_path / "handoff.db")),
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    with pytest.raises(TypeError):
        service._record_ref("mystery", "docs/unknown.md", None, None, "codex/gpt-5.4")


def test_record_ref_requires_keyword_verdict(tmp_path: Path) -> None:
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()

    service = HandoffService(
        store=SQLiteClient(db_path=str(tmp_path / "handoff.db")),
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    with pytest.raises(TypeError):
        service._record_ref("audit", "docs/unknown.md", "codex/gpt-5.4", "BLOCK")


def test_get_handoff_events_excludes_non_handoff_runtime_events(tmp_path: Path) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
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
        git_client=StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
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
    """Both active and passive events should be shown."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "plan_recorded", "codex/gpt-5.4", detail="auto plan")
    store.add_event(branch, "handoff_plan", "codex/gpt-5.4", detail="plan ready")

    events = service.get_handoff_events(branch)

    assert [event.event_type for event in events] == ["handoff_plan", "plan_recorded"]


def test_get_handoff_events_keeps_recorded_run_when_no_active_handoff(
    tmp_path: Path,
) -> None:
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "report_recorded", "codex/gpt-5.4", detail="auto run")

    events = service.get_handoff_events(branch)

    assert [event.event_type for event in events] == ["report_recorded"]


def test_get_success_handoff_events_filters_passive_only(
    tmp_path: Path,
) -> None:
    """Verify get_success_handoff_events excludes passive fallbacks."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "plan_recorded", "codex/gpt-5.4", detail="auto plan")
    store.add_event(branch, "handoff_plan", "codex/gpt-5.4", detail="plan ready")
    store.add_event(branch, "handoff_indicate", "manager", detail="manager indicate")
    store.add_event(branch, "handoff_audit", "codex/gpt-5.4", detail="audit ready")
    store.add_event(branch, "audit_recorded", "codex/gpt-5.4", detail="auto audit")
    store.add_event(branch, "handoff_verdict", "manager", detail="verdict: MAJOR")

    success_events = service.get_success_handoff_events(branch)
    event_types = {e.event_type for e in success_events}

    assert "plan_recorded" not in event_types
    assert "audit_recorded" not in event_types
    assert "handoff_plan" in event_types
    assert "handoff_audit" in event_types
    assert "handoff_indicate" in event_types
    assert "handoff_verdict" in event_types


def test_get_success_handoff_events_applies_limit(tmp_path: Path) -> None:
    """Verify limit is applied after success filter."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-304"
    service = HandoffService(
        store=store,
        git_client=StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "handoff_plan", "codex/gpt-5.4", detail="oldest")
    store.add_event(branch, "handoff_report", "codex/gpt-5.4", detail="middle")
    store.add_event(branch, "handoff_audit", "codex/gpt-5.4", detail="newest")

    events = service.get_success_handoff_events(branch, limit=2)
    assert len(events) == 2
    assert events[0].event_type == "handoff_audit"
    assert events[1].event_type == "handoff_report"


def test_success_events_includes_legacy_handoff_run(tmp_path: Path) -> None:
    """Verify legacy handoff_run events are included in success events."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-581"
    service = HandoffService(
        store=store,
        git_client=StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "handoff_run", "codex/gpt-5.4", detail="legacy report")

    events = service.get_success_handoff_events(branch)
    assert len(events) == 1
    assert events[0].event_type == "handoff_run"


class TestHandoffFailureDetection:
    def test_get_handoff_events_finds_blocker_kind(self, tmp_path: Path) -> None:
        worktree_root = tmp_path / "wt"
        git_common = tmp_path / ".git"
        worktree_root.mkdir()
        git_common.mkdir()

        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
        service = HandoffService(
            store=store,
            git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
        )

        store.add_event(
            "task/issue-304",
            "handoff_indicate",
            "manager",
            detail="Flow blocked due to dependency issue",
        )

        events = service.get_handoff_events("task/issue-304")
        assert len(events) == 1
        assert events[0].event_type == "handoff_indicate"
        assert "blocked" in events[0].detail

    def test_success_events_exclude_blocker_events(self, tmp_path: Path) -> None:
        worktree_root = tmp_path / "wt"
        git_common = tmp_path / ".git"
        worktree_root.mkdir()
        git_common.mkdir()

        store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
        service = HandoffService(
            store=store,
            git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
        )

        store.add_event(
            "task/issue-304", "handoff_plan", "planner", detail="Plan created"
        )
        store.add_event(
            "task/issue-304", "state_unchanged", "executor", detail="State unchanged"
        )
        store.add_event(
            "task/issue-304",
            "transition_count_exceeded",
            "executor",
            detail="Loop detected",
        )
        store.add_event(
            "task/issue-304", "handoff_report", "executor", detail="Report created"
        )

        success_events = service.get_success_handoff_events("task/issue-304")
        assert len(success_events) == 2
        event_types = [e.event_type for e in success_events]
        assert "handoff_plan" in event_types
        assert "handoff_report" in event_types
        assert "state_unchanged" not in event_types
        assert "transition_count_exceeded" not in event_types


def test_success_events_includes_next_step_set(tmp_path: Path) -> None:
    """Verify next_step_set events appear in get_success_handoff_events."""
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    branch = "task/issue-894"
    service = HandoffService(
        store=store,
        git_client=StubGitClient(tmp_path / "wt", tmp_path / ".git", branch),
    )

    store.add_event(branch, "next_step_set", "executor", detail="Next step test")
    store.add_event(branch, "handoff_report", "executor", detail="report ready")

    events = service.get_success_handoff_events(branch)
    event_types = [e.event_type for e in events]
    assert "next_step_set" in event_types
    assert "handoff_report" in event_types


def test_record_ref_skips_handoff_append_event(tmp_path: Path) -> None:
    """Verify _record_ref does not record duplicate handoff_append event."""
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    plan_path = worktree_root / "docs" / "plans" / "test.md"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text("plan content", encoding="utf-8")
    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-1678"),
    )
    handoff_file = (
        git_common / "vibe3" / "handoff" / "task-issue-1678-abc" / "current.md"
    )
    service.storage.ensure_current_handoff = MagicMock(return_value=handoff_file)
    service.storage.append_current_handoff = MagicMock(return_value=handoff_file)
    service.storage.normalize_ref_value = MagicMock(return_value="docs/plans/test.md")
    service._record_ref("plan", "docs/plans/test.md", actor="planner")
    events = service.get_handoff_events("task/issue-1678")
    handoff_plan_events = [e for e in events if e.event_type == "handoff_plan"]
    assert len(handoff_plan_events) == 1
    assert (
        handoff_plan_events[0].detail == "Recorded plan reference: docs/plans/test.md"
    )
    handoff_append_events = [e for e in events if e.event_type == "handoff_append"]
    assert len(handoff_append_events) == 0
    service.storage.append_current_handoff.assert_called_once()


def test_append_current_handoff_records_handoff_append_event(tmp_path: Path) -> None:
    """Verify append_current_handoff records a handoff_append event in SQLite."""
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    # Call append_current_handoff
    service.append_current_handoff(
        "Test context message",
        actor="init",
        kind="context",
        branch="task/issue-304",
    )

    # Verify handoff_append event was recorded
    events = store.get_events("task/issue-304", event_type="handoff_append")
    assert len(events) == 1
    assert events[0]["detail"] == "Test context message"
    assert events[0]["actor"] == "init"


def test_get_recent_updates_returns_chronological_order(tmp_path: Path) -> None:
    """Verify get_recent_updates returns entries in oldest-first order from file."""
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()

    from vibe3.utils.git_helpers import get_branch_handoff_dir

    handoff_dir = get_branch_handoff_dir(str(git_common), "task/issue-304")
    handoff_dir.mkdir(parents=True)

    # Use isoformat timestamps without tz offset (matching production format)
    handoff_file = handoff_dir / "current.md"
    handoff_file.write_text(
        """# Handoff: task/issue-304

## Updates

### 2026-06-24T10:00:00 | planner | plan
First entry - oldest

### 2026-06-24T11:00:00 | executor | run
Second entry - middle

### 2026-06-24T12:00:00 | reviewer | review
Third entry - newest
"""
    )

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    updates = service.storage.get_recent_updates(branch="task/issue-304", limit=None)

    assert len(updates) == 3
    # First entry should be oldest (file order)
    assert updates[0]["timestamp"] == "2026-06-24T10:00:00"
    assert updates[0]["actor"] == "planner"
    assert updates[0]["kind"] == "plan"
    assert updates[0]["message"] == "First entry - oldest"
    # Last entry should be newest
    assert updates[2]["timestamp"] == "2026-06-24T12:00:00"
    assert updates[2]["actor"] == "reviewer"
    assert updates[2]["kind"] == "review"
    assert updates[2]["message"] == "Third entry - newest"


def test_get_recent_updates_limit_returns_recent_n(tmp_path: Path) -> None:
    """Verify get_recent_updates with limit returns the last N entries."""
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()

    from vibe3.utils.git_helpers import get_branch_handoff_dir

    handoff_dir = get_branch_handoff_dir(str(git_common), "task/issue-304")
    handoff_dir.mkdir(parents=True)

    handoff_file = handoff_dir / "current.md"
    handoff_file.write_text(
        """# Handoff: task/issue-304

## Updates

### 2026-06-24T10:00:00 | planner | plan
First entry

### 2026-06-24T11:00:00 | executor | run
Second entry

### 2026-06-24T12:00:00 | reviewer | review
Third entry
"""
    )

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    # Default limit is 2
    updates = service.storage.get_recent_updates(branch="task/issue-304")

    assert len(updates) == 2
    # With limit=2, should get the LAST 2 entries, oldest-first
    assert updates[0]["timestamp"] == "2026-06-24T11:00:00"
    assert updates[0]["actor"] == "executor"
    assert updates[1]["timestamp"] == "2026-06-24T12:00:00"
    assert updates[1]["actor"] == "reviewer"


def test_get_recent_updates_empty_when_no_updates_section(tmp_path: Path) -> None:
    """Verify get_recent_updates returns empty list when no Updates heading."""
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()

    from vibe3.utils.git_helpers import get_branch_handoff_dir

    handoff_dir = get_branch_handoff_dir(str(git_common), "task/issue-304")
    handoff_dir.mkdir(parents=True)

    handoff_file = handoff_dir / "current.md"
    handoff_file.write_text("# Handoff: task/issue-304\n\nJust a plain handoff file.")

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    updates = service.storage.get_recent_updates(branch="task/issue-304")
    assert updates == []


def test_get_recent_updates_returns_empty_when_file_missing(tmp_path: Path) -> None:
    """Verify get_recent_updates returns empty list when no handoff file."""
    worktree_root = tmp_path / "wt"
    git_common = tmp_path / ".git"
    worktree_root.mkdir()
    git_common.mkdir()

    store = SQLiteClient(db_path=str(tmp_path / "handoff.db"))
    service = HandoffService(
        store=store,
        git_client=StubGitClient(worktree_root, git_common, "task/issue-304"),
    )

    updates = service.storage.get_recent_updates(branch="task/issue-304")
    assert updates == []
