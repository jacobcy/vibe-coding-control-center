"""Test plan file resolution across worktrees."""

from vibe3.roles.run_helpers import ensure_plan_file_exists


def test_ensure_plan_file_exists_with_absolute_path(tmp_path):
    """Absolute path that exists should pass."""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text("# Plan\n")

    # Should not raise
    ensure_plan_file_exists(str(plan_file))


def test_ensure_plan_file_exists_with_missing_absolute_path():
    """Absolute path that doesn't exist should raise."""
    import pytest

    with pytest.raises(FileNotFoundError):
        ensure_plan_file_exists("/nonexistent/path/plan.md")


def test_ensure_plan_file_exists_with_none():
    """None plan_file should be a no-op."""
    # Should not raise
    ensure_plan_file_exists(None)


def test_ensure_plan_file_exists_uses_resolve_handoff_target(tmp_path, monkeypatch):
    """Verify it uses resolve_handoff_target for relative paths."""

    # Create a worktree with plan file
    worktree_root = tmp_path / "worktree"
    worktree_root.mkdir()
    plan_dir = worktree_root / "docs" / "plans"
    plan_dir.mkdir(parents=True)
    plan_file = plan_dir / "test-plan.md"
    plan_file.write_text("# Plan\n")

    calls = []

    def mock_resolve(target, branch=None, git_client=None):
        calls.append((target, branch))
        if str(target) == "docs/plans/test-plan.md" and branch == "task/test-branch":
            return plan_file
        raise FileNotFoundError(f"Mock: {target}")

    # Mock the import inside ensure_plan_file_exists
    monkeypatch.setattr(
        "vibe3.utils.path_helpers.resolve_handoff_target",
        mock_resolve,
    )

    # Should call resolve_handoff_target with branch
    ensure_plan_file_exists("docs/plans/test-plan.md", branch="task/test-branch")

    # Verify it was called with correct args
    assert len(calls) == 1
    assert calls[0] == ("docs/plans/test-plan.md", "task/test-branch")
