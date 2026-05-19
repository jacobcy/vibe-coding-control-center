from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.utils.path_helpers import (
    is_shared_handoff_ref,
    ref_to_handoff_cmd,
    resolve_handoff_target,
    resolve_ref_path,
    sanitize_event_detail_paths,
    to_display_target,
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
    assert result == "vibe3 handoff show --branch task/issue-476 docs/reports/audit.md"


def test_ref_to_handoff_cmd_docs_plans_with_branch() -> None:
    """Docs plans with branch get --branch format."""
    path = "docs/plans/plan.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-476")
    assert result == "vibe3 handoff show --branch task/issue-476 docs/plans/plan.md"


def test_ref_to_handoff_cmd_docs_without_branch() -> None:
    """Docs refs without branch get plain format."""
    path = "docs/reports/audit.md"
    result = ref_to_handoff_cmd(path, branch=None)
    assert result == "vibe3 handoff show docs/reports/audit.md"


def test_ref_to_handoff_cmd_non_handoff_path() -> None:
    """Non-handoff paths (temp/logs, etc.) return as-is."""
    path = "temp/logs/debug.log"
    result = ref_to_handoff_cmd(path, branch="task/issue-476")
    assert result == "temp/logs/debug.log"


def test_ref_to_handoff_cmd_absolute_path() -> None:
    """Absolute paths return as-is."""
    path = "/abs/path/to/file.md"
    result = ref_to_handoff_cmd(path, branch="task/issue-476")
    assert result == "/abs/path/to/file.md"


def test_ref_to_handoff_cmd_empty_string() -> None:
    """Empty string returns as-is."""
    result = ref_to_handoff_cmd("", branch="task/issue-476")
    assert result == ""


# --- resolve_handoff_target ---


def _make_git_client(git_common: str, worktree_root: str) -> MagicMock:
    client = MagicMock()
    client.get_git_common_dir.return_value = git_common
    client.get_worktree_root.return_value = worktree_root
    client.find_worktree_path_for_branch.return_value = None
    return client


def test_resolve_handoff_target_shared_artifact(tmp_path: Path) -> None:
    """@key resolves to git_common/vibe3/handoff/<key>."""
    artifact = tmp_path / "vibe3" / "handoff" / "task-123" / "run.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("content")

    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))
    result = resolve_handoff_target("@task-123/run.md", git_client=client)
    assert result == artifact


def test_resolve_handoff_target_shared_artifact_not_found(tmp_path: Path) -> None:
    """@key raises FileNotFoundError when artifact is missing."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))
    with pytest.raises(FileNotFoundError):
        resolve_handoff_target("@missing/run.md", git_client=client)


def test_resolve_handoff_target_absolute_path(tmp_path: Path) -> None:
    """Absolute path is returned directly (debug fallback)."""
    target_file = tmp_path / "file.md"
    target_file.write_text("content")

    client = _make_git_client(str(tmp_path), str(tmp_path))
    result = resolve_handoff_target(str(target_file), git_client=client)
    assert result == target_file


def test_resolve_handoff_target_canonical_ref_current_worktree(tmp_path: Path) -> None:
    """Relative path resolves to current worktree when no branch given."""
    ref_file = tmp_path / "docs" / "report.md"
    ref_file.parent.mkdir(parents=True)
    ref_file.write_text("content")

    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path))
    result = resolve_handoff_target("docs/report.md", git_client=client)
    assert result == ref_file


def test_resolve_handoff_target_canonical_ref_with_branch(tmp_path: Path) -> None:
    """Relative path resolves to branch worktree when --branch given."""
    branch_wt = tmp_path / "wt-branch"
    ref_file = branch_wt / "docs" / "report.md"
    ref_file.parent.mkdir(parents=True)
    ref_file.write_text("content")

    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path / "wt-main"))
    client.find_worktree_path_for_branch.return_value = branch_wt
    result = resolve_handoff_target(
        "docs/report.md", branch="task/issue-99", git_client=client
    )
    assert result == ref_file


def test_resolve_handoff_target_not_found_raises(tmp_path: Path) -> None:
    """Unresolvable target raises FileNotFoundError."""
    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path / "wt"))
    with pytest.raises(FileNotFoundError):
        resolve_handoff_target("docs/nonexistent.md", git_client=client)


def test_resolve_handoff_target_branch_strict_no_fallback(tmp_path: Path) -> None:
    """When --branch given, file missing from branch worktree → error."""
    branch_wt = tmp_path / "wt-branch"
    branch_wt.mkdir()
    # File exists in CWD but NOT in branch worktree
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "report.md").write_text("wrong-flow-content")

    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path))
    client.find_worktree_path_for_branch.return_value = branch_wt

    with pytest.raises(FileNotFoundError, match="branch 'task/issue-99' worktree"):
        resolve_handoff_target(
            "docs/report.md", branch="task/issue-99", git_client=client
        )


def test_resolve_handoff_target_branch_no_worktree_raises(tmp_path: Path) -> None:
    """When --branch given but no worktree found → error immediately."""
    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path / "wt"))
    client.find_worktree_path_for_branch.return_value = None

    with pytest.raises(FileNotFoundError, match="No worktree found for branch"):
        resolve_handoff_target(
            "docs/report.md", branch="task/issue-99", git_client=client
        )


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


# --- Security Tests: Path Traversal Prevention ---


def test_resolve_shared_artifact_rejects_path_traversal_dot_dot(
    tmp_path: Path,
) -> None:
    """Branch name with '..' should be rejected."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))

    with pytest.raises(ValueError, match="path traversal sequence"):
        resolve_handoff_target(
            "@current", branch="../../../etc/passwd", git_client=client
        )


def test_resolve_shared_artifact_rejects_relative_traversal(tmp_path: Path) -> None:
    """Branch name containing '..' anywhere should be rejected."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))

    with pytest.raises(ValueError, match="path traversal sequence"):
        resolve_handoff_target(
            "@current", branch="task/issue-123/../../.env", git_client=client
        )


def test_resolve_shared_artifact_rejects_trailing_newline(
    tmp_path: Path,
) -> None:
    """Branch name with trailing newline should be rejected (Copilot review fix)."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))

    # re.match() with $ anchor would accept this, but fullmatch() rejects it
    with pytest.raises(ValueError, match="invalid characters"):
        resolve_handoff_target("@current", branch="valid\n", git_client=client)


def test_resolve_shared_artifact_rejects_control_chars(tmp_path: Path) -> None:
    """Branch name with control characters should be rejected."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))

    with pytest.raises(ValueError, match="invalid characters"):
        resolve_handoff_target("@current", branch="branch\0name", git_client=client)


def test_resolve_shared_artifact_accepts_valid_branch(tmp_path: Path) -> None:
    """Valid branch name should resolve successfully."""
    # Setup: create handoff directory for valid branch
    from vibe3.utils.git_helpers import get_branch_handoff_dir

    git_common = str(tmp_path / ".git")
    branch = "task/issue-823"
    handoff_dir = get_branch_handoff_dir(git_common, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    current_md = handoff_dir / "current.md"
    current_md.write_text("test content")

    client = _make_git_client(git_common, str(tmp_path / "wt"))

    result = resolve_handoff_target("@current", branch=branch, git_client=client)
    assert result == current_md


def test_resolve_shared_artifact_rejects_empty_branch(tmp_path: Path) -> None:
    """Empty branch name should be rejected."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))
    # Mock get_current_branch to return empty string
    client.get_current_branch.return_value = ""

    with pytest.raises(ValueError, match="cannot be empty"):
        resolve_handoff_target("@current", branch=None, git_client=client)


def test_resolve_shared_artifact_allows_single_dot_in_branch_name(
    tmp_path: Path,
) -> None:
    """Branch names with single dots should be valid (e.g., release/v1.0.0)."""
    # Setup: create handoff directory for branch with dots
    from vibe3.utils.git_helpers import get_branch_handoff_dir

    git_common = str(tmp_path / ".git")
    branch = "release/v1.0.0"
    handoff_dir = get_branch_handoff_dir(git_common, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    current_md = handoff_dir / "current.md"
    current_md.write_text("test content")

    client = _make_git_client(git_common, str(tmp_path / "wt"))

    result = resolve_handoff_target("@current", branch=branch, git_client=client)
    assert result == current_md


def test_resolve_shared_artifact_allows_multiple_single_dots(
    tmp_path: Path,
) -> None:
    """Branch names with multiple single dots should be valid (e.g., feature/api.v2)."""
    # Setup: create handoff directory for branch with multiple dots
    from vibe3.utils.git_helpers import get_branch_handoff_dir

    git_common = str(tmp_path / ".git")
    branch = "feature/api.v2"
    handoff_dir = get_branch_handoff_dir(git_common, branch)
    handoff_dir.mkdir(parents=True, exist_ok=True)
    current_md = handoff_dir / "current.md"
    current_md.write_text("test content")

    client = _make_git_client(git_common, str(tmp_path / "wt"))

    result = resolve_handoff_target("@current", branch=branch, git_client=client)
    assert result == current_md


def test_resolve_shared_artifact_rejects_path_traversal_in_key(
    tmp_path: Path,
) -> None:
    """Standard shared path key with '..' should be rejected."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))

    with pytest.raises(ValueError, match="path traversal sequence"):
        resolve_handoff_target("@../../../etc/passwd", git_client=client)


def test_resolve_shared_artifact_rejects_relative_traversal_in_key(
    tmp_path: Path,
) -> None:
    """Standard shared path key containing '..' should be rejected."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))

    with pytest.raises(ValueError, match="path traversal sequence"):
        resolve_handoff_target("@task/issue-123/../../.env", git_client=client)


def test_resolve_shared_artifact_rejects_empty_key(tmp_path: Path) -> None:
    """Empty key (just '@') should be rejected."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))

    with pytest.raises(ValueError, match="cannot be empty"):
        resolve_handoff_target("@", git_client=client)


def test_resolve_shared_artifact_rejects_control_chars_in_key(
    tmp_path: Path,
) -> None:
    """Key with control characters should be rejected."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))

    with pytest.raises(ValueError, match="invalid characters"):
        resolve_handoff_target("@task\x00name", git_client=client)


def test_resolve_shared_artifact_accepts_valid_key(tmp_path: Path) -> None:
    """Valid key should resolve successfully."""
    artifact = tmp_path / "vibe3" / "handoff" / "task-123" / "run.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("content")

    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))
    result = resolve_handoff_target("@task-123/run.md", git_client=client)
    assert result == artifact
