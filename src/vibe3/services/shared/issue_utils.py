"""Issue utilities: body management and context loading."""

import re
from typing import Final, Literal, cast

from vibe3.clients.github_client import GitHubClient
from vibe3.exceptions import UserError
from vibe3.models import IssueInfo
from vibe3.models.issue_body import FlowStateProjection
from vibe3.models.orchestra_config import OrchestraConfig

# Managed section markers
MANAGED_SECTION_START: Final[str] = "<!-- vibe3-flow-state-start -->"
MANAGED_SECTION_END: Final[str] = "<!-- vibe3-flow-state-end -->"
MANAGED_SECTION_PATTERN = re.compile(
    rf"{MANAGED_SECTION_START}(.*?){MANAGED_SECTION_END}",
    re.DOTALL,
)


def parse_projection(body: str) -> FlowStateProjection:
    """Parse flow-state projection from issue body.

    Args:
        body: Full issue body text

    Returns:
        FlowStateProjection (default if not found)
    """
    match = MANAGED_SECTION_PATTERN.search(body)
    if not match:
        return FlowStateProjection()

    section = match.group(1).strip()
    if not section:
        return FlowStateProjection()

    # Parse key-value pairs
    state: str = "active"
    blocked_by: list[int] = []
    blocked_reason: str | None = None
    dependencies: list[int] = []

    for line in section.split("\n"):
        line = line.strip()
        if not line:
            continue

        if line.startswith("- **State**:"):
            value = line.split(":", 1)[1].strip()
            if value in ("active", "blocked", "done", "aborted"):
                state = value

        elif line.startswith("- **Blocked by**:"):
            nums = line.split(":", 1)[1].strip()
            blocked_by = [int(n) for n in re.findall(r"\d+", nums)]

        elif line.startswith("- **Blocked reason**:"):
            blocked_reason = line.split(":", 1)[1].strip() or None

        elif line.startswith("- **Dependencies**:"):
            nums = line.split(":", 1)[1].strip()
            dependencies = [int(n) for n in re.findall(r"\d+", nums)]

    return FlowStateProjection(
        state=cast(Literal["active", "blocked", "done", "aborted"], state),
        blocked_by=blocked_by,
        blocked_reason=blocked_reason,
        dependencies=dependencies,
    )


def render_projection(proj: FlowStateProjection) -> str:
    """Render flow-state projection to managed section.

    Args:
        proj: FlowStateProjection instance

    Returns:
        Formatted managed section text
    """
    if proj.is_empty():
        return ""

    lines = [
        MANAGED_SECTION_START,
        "",
        "**Vibe3 Flow State**",
        "",
        f"- **State**: {proj.state}",
    ]

    if proj.blocked_by:
        blocked_str = ", ".join(f"#{n}" for n in proj.blocked_by)
        lines.append(f"- **Blocked by**: {blocked_str}")

    if proj.blocked_reason:
        lines.append(f"- **Blocked reason**: {proj.blocked_reason}")

    if proj.dependencies:
        deps_str = ", ".join(f"#{n}" for n in proj.dependencies)
        lines.append(f"- **Dependencies**: {deps_str}")

    lines.extend(["", MANAGED_SECTION_END])
    return "\n".join(lines)


def merge_projection(body: str, proj: FlowStateProjection) -> str:
    """Merge flow-state projection into issue body.

    Preserves user content, replaces managed section.

    Args:
        body: Original issue body
        proj: FlowStateProjection instance

    Returns:
        Merged body text
    """
    rendered = render_projection(proj)

    # Remove existing managed section
    cleaned = MANAGED_SECTION_PATTERN.sub("", body).strip()

    # Append new section if non-empty
    if not rendered:
        return cleaned

    return f"{cleaned}\n\n{rendered}"


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
