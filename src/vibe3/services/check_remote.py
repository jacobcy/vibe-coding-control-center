"""Remote index synchronization for check service."""

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.models.flow import IssueLink
from vibe3.models.orchestration import IssueState


@dataclass
class InitResult:
    """Result of remote index initialization."""

    total_flows: int
    updated: int
    skipped: int
    unresolvable: list[str] = field(default_factory=list)


if TYPE_CHECKING:
    pass


def issue_state_from_payload(issue: object) -> IssueState | None:
    """Extract issue state from GitHub payload."""
    if not isinstance(issue, dict):
        return None
    labels = issue.get("labels")
    if not isinstance(labels, list):
        return None
    for item in labels:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not isinstance(name, str):
            continue
        parsed = IssueState.from_label(name)
        if parsed is not None:
            return parsed
    return None


def requires_handoff(issue_state: IssueState | None) -> bool:
    """Check if issue state requires handoff file."""
    return issue_state in {
        IssueState.CLAIMED,
        IssueState.HANDOFF,
        IssueState.IN_PROGRESS,
        IssueState.REVIEW,
    }


def resolve_task_issue_number(
    branch: str,
    flow_data: dict[str, object],
    issue_links: list[dict[str, object]],
) -> int | None:
    """Resolve task issue number from branch or flow data."""
    task_issue = flow_data.get("task_issue_number") or IssueLink.resolve_task_number(
        issue_links
    )
    if task_issue:
        return int(str(task_issue))

    match = re.fullmatch(r"task/issue-(\d+)", branch)
    if match:
        return int(match.group(1))
    return None


def is_empty_auto_scene(flow_data: dict[str, object]) -> bool:
    """Check if flow has empty auto scene markers.

    Note: manager_session_id, planner_session_id, executor_session_id, and
    reviewer_session_id are deprecated fields. They are kept for backward
    compatibility but should not be used for runtime session checks.
    Use runtime_session registry instead.
    """
    markers = (
        # Deprecated: use runtime_session registry instead
        "manager_session_id",
        "planner_session_id",
        "executor_session_id",
        "reviewer_session_id",
        # Non-deprecated markers
        "plan_ref",
        "report_ref",
        "audit_ref",
        "planner_status",
        "executor_status",
        "reviewer_status",
        "execution_pid",
        "execution_started_at",
        "execution_completed_at",
    )
    return not any(flow_data.get(marker) for marker in markers)


class CheckRemote:
    """Mixin for remote index initialization operations."""

    def init_remote_index(self, pr_limit: int = 50) -> InitResult:
        """From remote sync flow state (mostly back-filling task_issue_number)."""
        logger.bind(domain="check", pr_limit=pr_limit).info("Initializing remote index")

        branch_issue_map: dict[str, list[int]] = {}

        # Path A: merged PR body
        # self is assumed to be CheckService
        this = cast(Any, self)

        for pr in this.github_client.list_merged_prs(limit=pr_limit):
            branch_name = pr.get("headRefName", "")
            if not branch_name:
                continue
            for n in parse_linked_issues(pr.get("body") or ""):
                branch_issue_map.setdefault(branch_name, [])
                if n not in branch_issue_map[branch_name]:
                    branch_issue_map[branch_name].append(n)
        logger.bind(
            domain="check", path="pr_body", branches_resolved=len(branch_issue_map)
        ).info("Remote index build done (Path A)")

        all_flows = this.store.get_all_flows()
        updated, skipped, unresolvable = 0, 0, []

        for flow in all_flows:
            branch = flow["branch"]
            # Skip if already has task_issue_number resolved.
            existing_links = this.store.get_issue_links(branch)

            if IssueLink.resolve_task_number(existing_links):
                skipped += 1
                continue

            # Resolve from map
            issues = branch_issue_map.get(branch)
            if not issues:
                unresolvable.append(branch)
                continue

            # Update first one as task
            from vibe3.services.task_service import TaskService

            TaskService(store=this.store).link_issue(
                branch, issues[0], "task", actor="check:init"
            )
            updated += 1

        return InitResult(
            total_flows=len(all_flows),
            updated=updated,
            skipped=skipped,
            unresolvable=unresolvable,
        )
