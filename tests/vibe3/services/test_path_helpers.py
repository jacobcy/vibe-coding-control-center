from pathlib import Path

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
        {"ref": abs_ref, "verdict": "UNKNOWN"},
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
    result = ref_to_handoff_cmd(path, branch=None)
    assert result == "vibe3 handoff show @task-476/run-1.md"


def test_ref_to_handoff_cmd_docs_reports_with_branch() -> None:
    """Docs reports with branch get --branch format."""
    path = "docs/reports/audit.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-476")
    assert result == "vibe3 handoff show --branch task/issue-476 @report"


def test_ref_to_handoff_cmd_docs_plans_with_branch() -> None:
    """Docs plans with branch get --branch format."""
    path = "docs/plans/plan.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-476")
    assert result == "vibe3 handoff show --branch task/issue-476 @plan"


def test_ref_to_handoff_cmd_docs_without_branch() -> None:
    """Docs refs without branch get plain format."""
    path = "docs/reports/audit.md"
    result = ref_to_handoff_cmd(path, branch=None)
    assert result == "vibe3 handoff show @report"


def test_ref_to_handoff_cmd_non_handoff_path() -> None:
    """Non-handoff paths (temp/logs, etc.) are wrapped in vibe3 handoff show."""
    path = "temp/logs/debug.log"
    result = ref_to_handoff_cmd(path, branch="task/issue-476")
    assert result == "vibe3 handoff show --branch task/issue-476 temp/logs/debug.log"


def test_ref_to_handoff_cmd_absolute_path() -> None:
    """Absolute paths are wrapped in vibe3 handoff show to avoid permission issues."""
    path = "/abs/path/to/file.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-476")
    assert result == "vibe3 handoff show --branch task/issue-476 /abs/path/to/file.md"


def test_ref_to_handoff_cmd_empty_string() -> None:
    """Empty string is wrapped in vibe3 handoff show."""
    result = ref_to_handoff_cmd("", branch="task/issue-476")
    assert result == "vibe3 handoff show --branch task/issue-476"


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
