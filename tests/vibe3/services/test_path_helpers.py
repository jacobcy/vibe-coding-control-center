from pathlib import Path

import pytest

from vibe3.services.handoff_resolution import (
    is_shared_handoff_ref,
    to_display_target,
)
from vibe3.services.path_helpers import (
    ref_to_handoff_cmd,
    resolve_ref_path,
    sanitize_event_detail_paths,
)


def test_sanitize_event_detail_paths_rewrites_absolute_refs() -> None:
    worktree_root = "/workspace/vibe-center/.worktrees/task/issue-417"
    abs_ref = (
        "/workspace/vibe-center/.worktrees/task/issue-417/"
        "docs/reports/task-issue-417-audit-auto-2026-04-21T01:41:01Z.md"
    )

    result = sanitize_event_detail_paths(
        f"Recorded audit reference: {abs_ref}",
        {"audit_ref": abs_ref, "verdict": "UNKNOWN"},
        worktree_root=worktree_root,
    )

    assert abs_ref not in result
    assert "docs/reports/task-issue-417-audit-auto-2026-04-21T01:41:01Z.md" in result


def test_sanitize_event_detail_paths_rewrites_log_path_to_basename() -> None:
    log_path = "/tmp/temp/logs/ses_bad.async.log"

    result = sanitize_event_detail_paths(
        f"See log: {log_path}",
        {"log_path": log_path},
    )

    assert log_path not in result
    assert "ses_bad.async.log" in result


# --- is_shared_handoff_ref ---


def test_is_shared_handoff_ref_true_for_shared_prefix() -> None:
    assert is_shared_handoff_ref("vibe3/handoff/task-123/run-abc.md") is True


def test_is_shared_handoff_ref_false_for_worktree_ref() -> None:
    assert is_shared_handoff_ref("docs/reports/audit.md") is False


def test_is_shared_handoff_ref_false_for_absolute_path() -> None:
    assert is_shared_handoff_ref("/abs/path/to/file.md") is False


# --- to_display_target ---


def test_to_display_target_adds_at_prefix_for_shared() -> None:
    result = to_display_target("vibe3/handoff/task-123/run-abc.md")
    assert result == "@task-123/run-abc.md"


def test_to_display_target_returns_as_is_for_canonical_ref() -> None:
    ref = "docs/reports/audit.md"
    assert to_display_target(ref) == ref


def test_to_display_target_returns_as_is_for_absolute_path() -> None:
    path = "/abs/path/to/file.md"
    assert to_display_target(path) == path


# --- ref_to_handoff_cmd ---


def test_ref_to_handoff_cmd_shared_artifact_with_at_prefix() -> None:
    """Shared artifacts get @ prefix format."""
    path = "vibe3/handoff/task-476/run-1.md"
    result = ref_to_handoff_cmd(path, branch=None, ref_field="report_ref")
    assert result == "vibe3 handoff show @report"


def test_ref_to_handoff_cmd_docs_reports_with_branch() -> None:
    """Docs reports with branch get --branch format."""
    path = "docs/reports/audit.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-476", ref_field="report_ref")
    assert result == "vibe3 handoff show --branch task/issue-476 @report"


def test_ref_to_handoff_cmd_docs_plans_with_branch() -> None:
    """Docs plans with branch get --branch format."""
    path = "docs/plans/plan.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-476", ref_field="plan_ref")
    assert result == "vibe3 handoff show --branch task/issue-476 @plan"


def test_ref_to_handoff_cmd_docs_without_branch() -> None:
    """Docs refs without branch get plain format."""
    path = "docs/reports/audit.md"
    result = ref_to_handoff_cmd(path, branch=None, ref_field="audit_ref")
    assert result == "vibe3 handoff show @audit"


def test_ref_to_handoff_cmd_non_handoff_path() -> None:
    """Non-handoff paths now require ref_field, return handoff command."""
    path = "temp/logs/debug.log"
    result = ref_to_handoff_cmd(path, branch="task/issue-476", ref_field="plan_ref")
    assert result == "vibe3 handoff show --branch task/issue-476 @plan"


def test_ref_to_handoff_cmd_absolute_path() -> None:
    """Absolute paths now require ref_field, return handoff command."""
    path = "/abs/path/to/file.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-476", ref_field="plan_ref")
    assert result == "vibe3 handoff show --branch task/issue-476 @plan"


def test_ref_to_handoff_cmd_empty_string() -> None:
    """Empty string now requires ref_field, return handoff command."""
    result = ref_to_handoff_cmd("", branch="task/issue-476", ref_field="plan_ref")
    assert result == "vibe3 handoff show --branch task/issue-476 @plan"


# --- ref_to_handoff_cmd with ref_field parameter ---


def test_ref_to_handoff_cmd_with_ref_field_indicate_ref() -> None:
    """ref_field parameter uses field-to-alias mapping for indicate_ref."""
    path = "docs/plans/issue-123-plan.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-123", ref_field="indicate_ref")
    assert result == "vibe3 handoff show --branch task/issue-123 @indicate"


def test_ref_to_handoff_cmd_with_ref_field_audit_ref() -> None:
    """ref_field parameter uses field-to-alias mapping for audit_ref."""
    path = "docs/reports/issue-123-audit.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-123", ref_field="audit_ref")
    assert result == "vibe3 handoff show --branch task/issue-123 @audit"


def test_ref_to_handoff_cmd_with_ref_field_plan_ref() -> None:
    """ref_field parameter with plan_ref produces same result as path-based."""
    path = "docs/plans/plan.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-123", ref_field="plan_ref")
    # Should match path-based behavior: @plan alias
    assert result == "vibe3 handoff show --branch task/issue-123 @plan"


def test_ref_to_handoff_cmd_with_ref_field_report_ref() -> None:
    """ref_field parameter with report_ref produces same result as path-based."""
    path = "docs/reports/report.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-123", ref_field="report_ref")
    # Should match path-based behavior: @report alias
    assert result == "vibe3 handoff show --branch task/issue-123 @report"


def test_ref_to_handoff_cmd_with_ref_field_shared_artifact() -> None:
    """ref_field parameter works with shared artifact paths."""
    path = "vibe3/handoff/task-1/run.md"
    result = ref_to_handoff_cmd(path, ref_field="indicate_ref")
    # Shared artifacts use @indicate alias without --branch
    assert result == "vibe3 handoff show @indicate"


def test_ref_to_handoff_cmd_with_ref_field_unknown_field() -> None:
    """Unknown ref_field raises ValueError."""
    path = "docs/reports/audit.md"
    with pytest.raises(ValueError, match="Unknown ref_field"):
        ref_to_handoff_cmd(path, branch="task/issue-123", ref_field="unknown_ref")


def test_ref_to_handoff_cmd_with_ref_field_none() -> None:
    """ref_field=None raises ValueError (no path-based fallback)."""
    path = "docs/reports/audit.md"
    with pytest.raises(ValueError, match="ref_field is required"):
        ref_to_handoff_cmd(path, branch="task/issue-123", ref_field=None)


# --- resolve_ref_path ---


def test_resolve_ref_path_cross_machine_handoff_path(tmp_path: Path) -> None:
    """Handoff paths from other machines should be converted to relative."""
    # Path from different machine (not current git_common)
    cross_machine_path = (
        "/Users/other/src/repo/.git/vibe3/handoff/task-123/run-2026-03-27.md"
    )
    result = resolve_ref_path(cross_machine_path, worktree_root=str(tmp_path))
    assert result == "vibe3/handoff/task-123/run-2026-03-27.md"


def test_resolve_ref_path_non_handoff_absolute_path(tmp_path: Path) -> None:
    """Non-handoff absolute paths should stay absolute."""
    non_handoff_path = "/Users/other/src/repo/docs/report.md"
    result = resolve_ref_path(non_handoff_path, worktree_root=str(tmp_path))
    # Should return as absolute since it doesn't match any pattern
    assert result == non_handoff_path


# --- ref_to_handoff_cmd parameter validation ---


def test_ref_to_handoff_cmd_requires_ref_field() -> None:
    """ref_field is required, raises ValueError if None."""
    with pytest.raises(ValueError, match="ref_field is required"):
        ref_to_handoff_cmd("docs/plans/test.md", branch="task/issue-123")


def test_ref_to_handoff_cmd_rejects_unknown_ref_field() -> None:
    """Unknown ref_field raises ValueError."""
    with pytest.raises(ValueError, match="Unknown ref_field"):
        ref_to_handoff_cmd(
            "docs/plans/test.md", branch="task/issue-123", ref_field="unknown_ref"
        )


def test_ref_to_handoff_cmd_ref_field_validation() -> None:
    """Valid ref_field values work correctly."""
    valid_fields = ["plan_ref", "report_ref", "audit_ref", "indicate_ref", "spec_ref"]
    for ref_field in valid_fields:
        result = ref_to_handoff_cmd(
            "docs/plans/test.md", branch="task/issue-123", ref_field=ref_field
        )
        assert "vibe3 handoff show" in result
