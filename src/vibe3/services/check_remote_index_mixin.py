"""Check service remote index operations."""

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues


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
        """从 branch_issue_map 创建/更新 flows。

        对于 merged PRs：
        - 如果 flow 不存在，创建并设置状态为 done
        - 如果 flow 存在但没有 task_issue_number，回填
        - 如果 flow 已有 task_issue_number，跳过

        Returns:
            (updated_count, skipped_count, unresolvable_branches)
        """
        updated, skipped, unresolvable = 0, 0, []
        existing_flows = {f["branch"]: f for f in self.store.get_all_flows()}

        # Process all branches from merged PRs
        for branch, issues_for_branch in branch_issue_map.items():
            if not issues_for_branch:
                unresolvable.append(branch)
                continue

            task_issue, extra_issues = issues_for_branch[0], issues_for_branch[1:]

            # Check if flow exists
            if branch in existing_flows:
                flow = existing_flows[branch]
                if flow.get("task_issue_number"):
                    skipped += 1
                    continue
                # Update existing flow
                self.store.update_flow_state(
                    branch, task_issue_number=task_issue, latest_actor="check --init"
                )
            else:
                # Create new flow for merged PR
                flow_slug = branch.split("/")[-1] if "/" in branch else branch
                self.store.update_flow_state(
                    branch,
                    flow_slug=flow_slug,
                    task_issue_number=task_issue,
                    flow_status="done",
                    latest_actor="check --init",
                )

            # Add issue links
            self.store.add_issue_link(branch, task_issue, "task")
            self.store.add_event(
                branch,
                "issue_linked",
                "check --init",
                f"Issue #{task_issue} back-filled as task",
            )
            for extra in extra_issues:
                self.store.add_issue_link(branch, extra, "related")
                self.store.add_event(
                    branch,
                    "issue_linked",
                    "check --init",
                    f"Issue #{extra} back-filled as related",
                )
            logger.bind(domain="check", branch=branch, task_issue=task_issue).info(
                "Back-filled task_issue_number"
            )
            updated += 1

        return updated, skipped, unresolvable
