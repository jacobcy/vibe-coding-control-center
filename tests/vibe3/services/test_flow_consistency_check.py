"""Tests for flow consistency check and recovery classification."""

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.services.flow.consistency import (
    FlowConsistencyCode,
    check_flow_consistency,
)


def _make_git_client(worktree_path=None, branch_exists=True):
    git = MagicMock()
    git.find_worktree_path_for_branch.return_value = worktree_path
    git.branch_exists.return_value = branch_exists
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


def _patch_check_ref_exists_returns_false():
    """Monkeypatch consistency.check_ref_exists to always report missing."""
    import vibe3.services.flow.consistency as mod

    orig = mod.check_ref_exists
    mod.check_ref_exists = lambda ref, branch, **kw: (ref, False)
    return orig


def test_missing_plan_ref_is_artifact_blocker_not_rebuild():
    """A recorded plan_ref whose file disappeared in an otherwise healthy
    worktree is an artifact repair blocker — the flow waits for explicit
    rebind/regeneration and is NOT auto-rebuilt (spec 012 US2, SC-002)."""
    git = _make_git_client(Path("/wt/task/issue-1"))
    state = {"worktree_path": "/wt/task/issue-1", "plan_ref": "docs/plans/missing.md"}
    import vibe3.services.flow.consistency as mod

    orig = _patch_check_ref_exists_returns_false()
    try:
        result = check_flow_consistency("task/issue-1", state, git_client=git)
        assert result.code == FlowConsistencyCode.MISSING_ARTIFACT
        assert not result.needs_rebuild
        assert result.ref_field == "plan_ref"
        assert result.ref_value == "docs/plans/missing.md"
    finally:
        mod.check_ref_exists = orig


def test_missing_spec_ref_is_artifact_blocker():
    """spec_ref disappearance shares the SAME artifact-blocker classification
    as plan/report/audit (FR-010 — one shared resolution contract, no
    special-casing for spec)."""
    git = _make_git_client(Path("/wt/task/issue-1"))
    state = {
        "worktree_path": "/wt/task/issue-1",
        "spec_ref": ".specify/specs/012-foo/spec.md",
    }
    import vibe3.services.flow.consistency as mod

    orig = _patch_check_ref_exists_returns_false()
    try:
        result = check_flow_consistency("task/issue-1", state, git_client=git)
        assert result.code == FlowConsistencyCode.MISSING_ARTIFACT
        assert not result.needs_rebuild
        assert result.ref_field == "spec_ref"
    finally:
        mod.check_ref_exists = orig


def test_present_spec_ref_still_ok_when_file_exists():
    """A healthy worktree with a resolvable spec_ref stays consistent (FR-010
    includes spec_ref without making it rebuild-triggering)."""
    git = _make_git_client(Path("/wt/task/issue-1"))
    state = {
        "worktree_path": "/wt/task/issue-1",
        "spec_ref": ".specify/specs/012-foo/spec.md",
        "plan_ref": "docs/plans/plan.md",
    }
    import vibe3.services.flow.consistency as mod

    orig = mod.check_ref_exists
    mod.check_ref_exists = lambda ref, branch, **kw: (ref, True)
    try:
        result = check_flow_consistency("task/issue-1", state, git_client=git)
        assert result.code == FlowConsistencyCode.OK
        assert not result.needs_rebuild
    finally:
        mod.check_ref_exists = orig


def test_non_task_branch_skips_recorded_check():
    """dev/ branches don't require recorded worktree_path."""
    git = _make_git_client(Path("/wt/dev/issue-1"))
    state = {}  # no worktree_path
    result = check_flow_consistency("dev/issue-1", state, git_client=git)
    assert result.code == FlowConsistencyCode.OK


def test_placeholder_flow_blocked_no_worktree_returns_ok():
    """Placeholder flow: blocked + no branch is a legal state."""
    git = _make_git_client(None, branch_exists=False)
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
