from __future__ import annotations

from vibe3.clients import GitHubClient
from vibe3.exceptions import UserError
from vibe3.models import IssueInfo, OrchestraConfig


def load_issue_info(
    issue_number: int,
    *,
    config: OrchestraConfig,
    github: GitHubClient | None = None,
) -> IssueInfo:
    """Load issue information from GitHub.

    Args:
        issue_number: GitHub issue number
        config: Orchestra configuration with repo information
        github: Optional GitHub client (creates default if None)

    Returns:
        IssueInfo with parsed issue data

    Raises:
        UserError: If issue cannot be loaded or parsed
    """
    github = github or GitHubClient()
    payload = github.view_issue(issue_number, repo=config.repo)

    if payload == "network_error":
        raise UserError(f"无法读取 issue #{issue_number}，请检查 GitHub 网络或认证状态")
    if payload is None or not isinstance(payload, dict):
        raise UserError(f"issue #{issue_number} 不存在或当前仓库不可访问")

    issue = IssueInfo.from_github_payload(payload)
    if issue is not None:
        return issue

    # Fallback for unparsed payloads
    title = str(payload.get("title") or f"Issue {issue_number}")
    labels = [
        label.get("name", "")
        for label in payload.get("labels", [])
        if isinstance(label, dict)
    ]
    return IssueInfo(number=issue_number, title=title, labels=labels)
