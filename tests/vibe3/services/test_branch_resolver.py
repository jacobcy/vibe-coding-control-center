"""Tests for branch_resolver service."""

from unittest.mock import Mock

from vibe3.models.pr import PRMetadata, PRResponse, PRState
from vibe3.services.branch_resolver import resolve_branch_from_pr


def test_resolve_branch_from_pr_via_closing_issue():
    """PR → Issue → Flow → Branch (标准路径)."""
    # Mock PR with closingIssuesReferences
    pr = PRResponse(
        number=996,
        title="fix: test",
        body="",
        state=PRState.OPEN,
        head_branch="test/issue-991",
        base_branch="main",
        url="https://github.com/test/pr/996",
        draft=False,
        is_ready=True,
        ci_passed=False,
        ci_status=None,
        metadata=PRMetadata(task_issue=991),
    )

    # Mock PRService
    pr_svc = Mock()
    pr_svc.github_client.get_pr.return_value = pr

    # Mock store.get_flows_by_issue
    flow_data = {"branch": "test/issue-991", "flow_slug": "issue_991"}
    pr_svc.store.get_flows_by_issue.return_value = [flow_data]

    # Call
    branch = resolve_branch_from_pr(996, pr_svc)

    # Verify
    assert branch == "test/issue-991"
    pr_svc.github_client.get_pr.assert_called_once_with(996)
    pr_svc.store.get_flows_by_issue.assert_called_once_with(991, role="task")


def test_resolve_branch_from_pr_no_flow():
    """PR 关联 Issue 但本地无 Flow → 返回 None."""
    pr = PRResponse(
        number=996,
        title="fix: test",
        body="",
        state=PRState.OPEN,
        head_branch="test/issue-999",
        base_branch="main",
        url="https://github.com/test/pr/996",
        draft=False,
        is_ready=True,
        ci_passed=False,
        ci_status=None,
        metadata=PRMetadata(task_issue=999),
    )

    pr_svc = Mock()
    pr_svc.github_client.get_pr.return_value = pr
    pr_svc.store.get_flows_by_issue.return_value = []  # 无 flow

    branch = resolve_branch_from_pr(996, pr_svc)

    assert branch is None
    pr_svc.github_client.get_pr.assert_called_once_with(996)


def test_resolve_branch_from_pr_no_issue():
    """PR 无 closingIssuesReferences → 返回 None."""
    pr = PRResponse(
        number=996,
        title="fix: test",
        body="",
        state=PRState.OPEN,
        head_branch="feature/demo",
        base_branch="main",
        url="https://github.com/test/pr/996",
        draft=False,
        is_ready=True,
        ci_passed=False,
        ci_status=None,
        metadata=None,  # 无 task_issue
    )

    pr_svc = Mock()
    pr_svc.github_client.get_pr.return_value = pr

    branch = resolve_branch_from_pr(996, pr_svc)

    assert branch is None
    pr_svc.github_client.get_pr.assert_called_once_with(996)
