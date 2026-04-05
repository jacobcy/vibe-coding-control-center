"""Remote index synchronization for check service."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.models.flow import IssueLink


@dataclass
class InitResult:
    """Result of remote index initialization."""

    total_flows: int
    updated: int
    skipped: int
    unresolvable: list[str] = field(default_factory=list)


if TYPE_CHECKING:
    pass


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
