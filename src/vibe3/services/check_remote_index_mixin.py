"""Check service remote index operations."""

from dataclasses import dataclass, field

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues


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
        """扫描远端，返回 branch → issue numbers 映射（两条路径合并）。"""
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
        ).info("Path A done")

        # 路径 B: GitHub Project items
        from vibe3.models.project_item import ProjectItemError as PIError
        from vibe3.services.task_service import TaskService

        client = TaskService(store=self.store)._get_project_client()
        if not client:
            logger.bind(domain="check").warning("Path B skipped: not configured")
            return branch_issue_map

        items = client.list_all_items()
        if isinstance(items, PIError):
            logger.bind(domain="check", error=items.message).warning("Path B failed")
            return branch_issue_map

        for item in items:
            if item.get("content_type") != "PullRequest":
                continue
            branch_name = item.get("head_ref_name") or ""
            if not branch_name:
                continue
            for n in item.get("closing_issues", []):
                branch_issue_map.setdefault(branch_name, [])
                if n not in branch_issue_map[branch_name]:
                    branch_issue_map[branch_name].append(n)
        logger.bind(
            domain="check",
            path="project_items",
            branches_resolved=len(branch_issue_map),
        ).info("Path B done")
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
            # Skip if already has task_issue_number in state (legacy)
            # or already has a task role issue linked (new truth).
            existing_links = self.store.get_issue_links(branch)
            has_task_link = any(lnk["issue_role"] == "task" for lnk in existing_links)

            if flow.get("task_issue_number") or has_task_link:
                skipped += 1
                continue
            issues_for_branch = branch_issue_map.get(branch, [])
            if not issues_for_branch:
                unresolvable.append(branch)
                continue

            task_issue, extra_issues = issues_for_branch[0], issues_for_branch[1:]
            # No longer backfill task_issue_number to flow_state.
            # Relationship truth is now in flow_issue_links.
            self.store.add_issue_link(branch, task_issue, "task")
            self.store.add_event(
                branch,
                "issue_linked",
                "check --init",
                f"Issue #{task_issue} bound as task (truth in flow_issue_links)",
            )
            for extra in extra_issues:
                self.store.add_issue_link(branch, extra, "repo")
                self.store.add_event(
                    branch,
                    "issue_linked",
                    "check --init",
                    f"Issue #{extra} bound as repo",
                )
            logger.bind(domain="check", branch=branch, task_issue=task_issue).info(
                "Bound task_issue_number (flow_issue_links)"
            )
            updated += 1

        return updated, skipped, unresolvable

    def init_remote_index(self, pr_limit: int = 200) -> InitResult:
        """全量扫描远端，绑定 flow 与 task issue 的关联关系到 flow_issue_links。

        路径 A — merged PR body 解析 Closes/Fixes/Resolves #xxx
        路径 B — GitHub Project items closingIssuesReferences
        已有 task role issue link 的 flow 跳过（不覆盖）。
        不回填远端真源字段到本地 SQLite（GitHub-as-truth）。
        """
        logger.bind(domain="check", action="init_remote_index").info(
            "Building remote index (PR body + GitHub Project items)"
        )
        branch_issue_map = self._build_branch_issue_map(pr_limit)
        updated, skipped, unresolvable = self._backfill_flows(branch_issue_map)
        return InitResult(
            total_flows=len(self.store.get_all_flows()),
            updated=updated,
            skipped=skipped,
            unresolvable=unresolvable,
        )
