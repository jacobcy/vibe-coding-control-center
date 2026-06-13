"""Tests for flow consistency check and recovery classification."""

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.services.flow.consistency import (
    FlowConsistencyCode,
    check_flow_consistency,
)


def _make_git_client(worktree_path=None):
    git = MagicMock()
    git.find_worktree_path_for_branch.return_value = worktree_path
    return git


def test_ok_when_worktree_and_recorded_path_match():
    git = _make_git_client(Path("/wt/task/issue-1"))
    state = {"worktree_path": "/wt/task/issue-1"}
    result = check_flow_consistency("task/issue-1", state, git_client=git)
    assert result.code == FlowConsistencyCode.OK
    assert not result.needs_rebuild


def test_missing_worktree_needs_rebuild():
    git = _make_git_client(None)
    state = {"worktree_path": "/wt/task/issue-1"}
    result = check_flow_consistency("task/issue-1", state, git_client=git)
    assert result.code == FlowConsistencyCode.MISSING_WORKTREE
    assert result.needs_rebuild


def test_missing_recorded_worktree_is_fixable():
    """Worktree exists physically but not recorded -- cheap fix, not rebuild."""
    git = _make_git_client(Path("/wt/task/issue-1"))
    state = {}  # no worktree_path in state
    result = check_flow_consistency("task/issue-1", state, git_client=git)
    assert result.code == FlowConsistencyCode.MISSING_RECORDED_WORKTREE
    assert not result.needs_rebuild  # NEW: fixable, not rebuild-worthy
    assert result.fix_action == "backfill_worktree_path"


def test_missing_ref_needs_rebuild():
    git = _make_git_client(Path("/wt/task/issue-1"))
    state = {"worktree_path": "/wt/task/issue-1", "plan_ref": "docs/plans/missing.md"}
    # Mock check_ref_exists to return False
    import vibe3.services.flow.consistency as mod

    orig = mod.check_ref_exists
    mod.check_ref_exists = lambda ref, branch, **kw: (ref, False)
    try:
        result = check_flow_consistency("task/issue-1", state, git_client=git)
        assert result.code == FlowConsistencyCode.MISSING_REF
        assert result.needs_rebuild
    finally:
        mod.check_ref_exists = orig


def test_non_task_branch_skips_recorded_check():
    """dev/ branches don't require recorded worktree_path."""
    git = _make_git_client(Path("/wt/dev/issue-1"))
    state = {}  # no worktree_path
    result = check_flow_consistency("dev/issue-1", state, git_client=git)
    assert result.code == FlowConsistencyCode.OK


def test_placeholder_flow_blocked_no_worktree_returns_ok():
    """Placeholder flow: blocked + no worktree is a legal state."""
    git = _make_git_client(None)
    state = {"flow_status": "blocked"}
    result = check_flow_consistency("task/issue-1", state, git_client=git)
    assert result.code == FlowConsistencyCode.OK
    assert not result.needs_rebuild


def test_blocked_flow_with_worktree_still_valid():
    """Blocked status alone doesn't skip valid worktree flows."""
    git = _make_git_client(Path("/wt/task/issue-1"))
    state = {"flow_status": "blocked", "worktree_path": "/wt/task/issue-1"}
    result = check_flow_consistency("task/issue-1", state, git_client=git)
    assert result.code == FlowConsistencyCode.OK
    assert not result.needs_rebuild
