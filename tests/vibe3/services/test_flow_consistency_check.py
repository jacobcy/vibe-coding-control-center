"""Tests for shared flow consistency detection."""

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.services.flow_consistency_check import (
    FlowConsistencyCode,
    check_flow_consistency,
)


def test_missing_worktree_requires_rebuild() -> None:
    """A recorded flow with no physical worktree must be rebuilt."""
    git_client = MagicMock()
    git_client.find_worktree_path_for_branch.return_value = None

    result = check_flow_consistency(
        "task/issue-303",
        {"branch": "task/issue-303", "worktree_path": "/tmp/missing"},
        git_client=git_client,
    )

    assert result.needs_rebuild is True
    assert result.code == FlowConsistencyCode.MISSING_WORKTREE


def test_missing_recorded_worktree_path_requires_rebuild(
    tmp_path: Path,
) -> None:
    """A task worktree that exists but is not recorded is an inconsistent scene."""
    git_client = MagicMock()
    git_client.find_worktree_path_for_branch.return_value = tmp_path

    result = check_flow_consistency(
        "task/issue-303",
        {"branch": "task/issue-303", "worktree_path": None},
        git_client=git_client,
    )

    assert result.needs_rebuild is True
    assert result.code == FlowConsistencyCode.MISSING_RECORDED_WORKTREE


def test_missing_ref_requires_rebuild(tmp_path: Path) -> None:
    """Missing refs should produce a rebuild recommendation, not label resume."""
    git_client = MagicMock()
    git_client.find_worktree_path_for_branch.return_value = tmp_path
    (tmp_path / "docs" / "plans").mkdir(parents=True)

    result = check_flow_consistency(
        "task/issue-303",
        {
            "branch": "task/issue-303",
            "worktree_path": str(tmp_path),
            "plan_ref": "docs/plans/missing.md",
        },
        git_client=git_client,
    )

    assert result.needs_rebuild is True
    assert result.code == FlowConsistencyCode.MISSING_REF
    assert result.ref_field == "plan_ref"
