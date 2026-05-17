"""Branch resolution services for PR → Flow mapping."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.models.pr import PRResponse
    from vibe3.services.pr_service import PRService


def resolve_branch_from_pr(
    pr_number: int | None,
    pr_svc: "PRService",
    pr: "PRResponse | None" = None,
) -> str | None:
    """Resolve branch from PR via Issue → Flow mapping (local database).

    Standard path (Issue #999):
        PR → closingIssuesReferences → Issue
        Issue → flow_issue_links → Flow
        Flow → branch

    Args:
        pr_number: PR number (optional if pr provided)
        pr_svc: PRService instance (provides github_client and store)
        pr: Already-fetched PR response (optional, avoids duplicate API call)

    Returns:
        Branch name if flow exists, None otherwise.

    Note:
        - No fallback to pr.head_branch (遵循 Issue #999 标准路径)
        - 无 flow → 静默返回 None (不报错、不警告)
        - Optimized: accepts pre-fetched PR to avoid duplicate API calls
    """
    # 1. Get PR metadata (use provided PR or fetch)
    if pr is None and pr_number:
        pr = pr_svc.github_client.get_pr(pr_number)

    if not pr or not pr.metadata or not pr.metadata.task_issue:
        return None

    # 2. Query Issue → Flow mapping using IssueFlowService (deterministic selection)
    issue_number = pr.metadata.task_issue
    from vibe3.services.issue_flow_service import IssueFlowService

    issue_flow_svc = IssueFlowService(store=pr_svc.store)
    flow = issue_flow_svc.find_active_flow(issue_number)

    # 3. Return flow's branch if exists
    if flow:
        return str(flow.get("branch"))

    # 4. No local flow → silent skip
    return None
