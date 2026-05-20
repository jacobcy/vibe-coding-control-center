"""Security tests for handoff target resolution.

Tests path traversal prevention and input validation.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.utils.handoff_resolution import resolve_handoff_target


def _make_git_client(git_common: str, worktree_root: str) -> MagicMock:
    client = MagicMock()
    client.get_git_common_dir.return_value = git_common
    client.get_worktree_root.return_value = worktree_root
    client.find_worktree_path_for_branch.return_value = None
    return client


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
