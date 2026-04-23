from vibe3.utils.path_helpers import sanitize_event_detail_paths


def test_sanitize_event_detail_paths_rewrites_absolute_refs() -> None:
    worktree_root = "/Users/jacobcy/src/vibe-center/main/.worktrees/task/issue-417"
    abs_ref = (
        "/Users/jacobcy/src/vibe-center/main/.worktrees/task/issue-417/"
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
