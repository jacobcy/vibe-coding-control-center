"""Check service remote index operations."""

from dataclasses import dataclass, field

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.models.flow import IssueLink


@dataclass
class InitResult:
    """Result of remote index init."""

    total_flows: int
    updated: int
    skipped: int
    unresolvable: list[str] = field(default_factory=list)


class CheckRemoteIndexMixin:
    """Mixin for remote index initialization operations."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        github_client: GitHubClient | None = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self.github_client = github_client or GitHubClient()

    def _build_branch_issue_map(self, pr_limit: int) -> dict[str, list[int]]:
        """扫描远端，返回 branch → issue numbers 映射。"""
        branch_issue_map: dict[str, list[int]] = {}

        # 路径 A: merged PR body
        for pr in self.github_client.list_merged_prs(limit=pr_limit):
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

        return branch_issue_map

    def _backfill_flows(
        self, branch_issue_map: dict[str, list[int]]
    ) -> tuple[int, int, list[str]]:
        """将 branch_issue_map 回填到本地 store。

        Returns:
            (updated_count, skipped_count, unresolvable_branches)
        """
        all_flows = self.store.get_all_flows()
        updated, skipped, unresolvable = 0, 0, []

        for flow in all_flows:
            branch = flow["branch"]
            # Skip if already has task_issue_number resolved.
            existing_links = self.store.get_issue_links(branch)

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

            TaskService(store=self.store).link_issue(
                branch, issues[0], "task", actor="check:init"
            )
            updated += 1

        return updated, skipped, unresolvable

    def init_remote_index(self, pr_limit: int = 50) -> InitResult:
        """从远端同步 flow 状态 (主要是回填 task_issue_number)。"""
        logger.bind(domain="check", pr_limit=pr_limit).info("Initializing remote index")

        branch_issue_map = self._build_branch_issue_map(pr_limit)
        updated, skipped, unresolvable = self._backfill_flows(branch_issue_map)
        return InitResult(
            total_flows=len(self.store.get_all_flows()),
            updated=updated,
            skipped=skipped,
            unresolvable=unresolvable,
        )
