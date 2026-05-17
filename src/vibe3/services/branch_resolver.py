"""Branch resolution services for PR → Flow mapping."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.services.pr_service import PRService


def resolve_branch_from_pr(pr_number: int, pr_svc: "PRService") -> str | None:
    """Resolve branch from PR via Issue → Flow mapping (local database).

    Standard path (Issue #999):
        PR → closingIssuesReferences → Issue
        Issue → flow_issue_links → Flow
        Flow → branch

    Args:
        pr_number: PR number
        pr_svc: PRService instance (provides github_client and store)

    Returns:
        Branch name if flow exists, None otherwise.

    Note:
        - No fallback to pr.head_branch (遵循 Issue #999 标准路径)
        - 无 flow → 静默返回 None (不报错、不警告)
    """
    # 1. Query PR metadata
    pr = pr_svc.github_client.get_pr(pr_number)
    if not pr or not pr.metadata or not pr.metadata.task_issue:
        return None

    # 2. Query Issue → Flow mapping (local SQLite)
    issue_number = pr.metadata.task_issue
    flow_links = pr_svc.store.get_flows_by_issue(issue_number, role="task")

    # 3. Return flow's branch if exists
    if flow_links:
        return str(flow_links[0]["branch"])

    # 4. No local flow → silent skip
    return None
