"""Tests for run_request module."""

from __future__ import annotations

from pathlib import Path

from vibe3.models import ExecutionRequest, IssueInfo, OrchestraConfig
from vibe3.roles.run_request import build_run_request


def test_build_run_request_publish_flag() -> None:
    """Test that commit_mode=True produces --publish flag."""
    config = OrchestraConfig(
        repo="test/repo",
        worktrees=Path("/tmp/worktrees"),
    )
    issue = IssueInfo(
        number=123,
        title="Test issue",
        state=None,
        labels=[],
        assignees=[],
    )

    # Test commit_mode=True produces --publish
    request = build_run_request(
        config=config,
        issue=issue,
        branch="task/issue-123-test",
        commit_mode=True,
    )

    assert isinstance(request, ExecutionRequest)
    assert "--publish" in request.cmd
    assert "--skill" not in request.cmd
    assert "vibe-commit" not in request.cmd
    assert "--no-async" in request.cmd
    assert "--branch" in request.cmd
    assert "task/issue-123-test" in request.cmd


def test_build_run_request_normal_mode() -> None:
    """Test that commit_mode=False does not produce --publish."""
    config = OrchestraConfig(
        repo="test/repo",
        worktrees=Path("/tmp/worktrees"),
    )
    issue = IssueInfo(
        number=456,
        title="Test issue",
        state=None,
        labels=[],
        assignees=[],
    )

    # Test commit_mode=False (normal run)
    request = build_run_request(
        config=config,
        issue=issue,
        branch="task/issue-456-test",
        commit_mode=False,
    )

    assert isinstance(request, ExecutionRequest)
    assert "--publish" not in request.cmd
    assert "--no-async" in request.cmd
    assert "--branch" in request.cmd


def test_build_run_request_with_plan_ref() -> None:
    """Test that plan_ref produces --plan flag."""
    config = OrchestraConfig(
        repo="test/repo",
        worktrees=Path("/tmp/worktrees"),
    )
    issue = IssueInfo(
        number=789,
        title="Test issue",
        state=None,
        labels=[],
        assignees=[],
    )

    # Test with plan_ref
    request = build_run_request(
        config=config,
        issue=issue,
        branch="task/issue-789-test",
        plan_ref="docs/plans/issue-789.md",
    )

    assert isinstance(request, ExecutionRequest)
    assert "--publish" not in request.cmd
    assert "--plan" in request.cmd
    assert "docs/plans/issue-789.md" in request.cmd
