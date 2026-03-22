"""Check service implementation."""

from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.utils.git_helpers import get_branch_handoff_dir


@dataclass
class CheckResult:
    """Result of consistency check."""

    is_valid: bool
    issues: list[str]
    branch: str = ""


@dataclass
class FixResult:
    """Result of auto-fix."""

    success: bool
    error: str | None = None


@dataclass
class InitResult:
    """Result of remote index init."""

    total_flows: int
    updated: int
    skipped: int
    unresolvable: list[str] = field(default_factory=list)


class CheckService:
    """Service for verifying handoff store consistency."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        github_client: GitHubClient | None = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()

    # ------------------------------------------------------------------
    # Single-branch check
    # ------------------------------------------------------------------

    def verify_current_flow(self, fix: bool = False) -> CheckResult:
        """Verify current branch flow consistency.

        Checks:
        - Flow record exists for current branch
        - task_issue_number exists on GitHub
        - Only one task issue per branch
        - pr_number matches current branch
        - plan_ref / report_ref / audit_ref files exist
        - shared current.md exists for active flow
        """
        logger.bind(domain="check", action="verify").info("Verifying flow consistency")

        branch = self.git_client.get_current_branch()
        return self._check_branch(branch)

    def _check_branch(self, branch: str) -> CheckResult:
        """Run all consistency checks for a single branch."""
        issues: list[str] = []

        flow_data = self.store.get_flow_state(branch)
        if not flow_data:
            return CheckResult(
                is_valid=False,
                issues=[f"No flow record for branch '{branch}'"],
                branch=branch,
            )

        # task issue exists on GitHub
        task_issue = flow_data.get("task_issue_number")
        if task_issue:
            issue = self.github_client.view_issue(task_issue)
            if not issue:
                issues.append(f"Task issue #{task_issue} not found on GitHub")

        # only one task issue per branch
        issue_links = self.store.get_issue_links(branch)
        task_issues = [lnk for lnk in issue_links if lnk["issue_role"] == "task"]
        if len(task_issues) > 1:
            issues.append(f"Multiple task issues for branch '{branch}'")

        # PR matches branch
        pr_number = flow_data.get("pr_number")
        if pr_number:
            pr = self.github_client.get_pr(pr_number)
            if pr and pr.head_branch != branch:
                issues.append(f"PR #{pr_number} does not match branch '{branch}'")

        # ref files exist
        for ref_field in ["plan_ref", "report_ref", "audit_ref"]:
            ref_value = flow_data.get(ref_field)
            if ref_value and not Path(ref_value).exists():
                issues.append(f"{ref_field} file not found: {ref_value}")

        # shared current.md
        git_dir = self.git_client.get_git_common_dir()
        handoff_path = get_branch_handoff_dir(git_dir, branch) / "current.md"
        if not handoff_path.exists():
            issues.append(f"Shared handoff file not found: {handoff_path}")

        is_valid = len(issues) == 0
        logger.bind(branch=branch, is_valid=is_valid, issues_count=len(issues)).info(
            "Check completed"
        )
        return CheckResult(is_valid=is_valid, issues=issues, branch=branch)

    # ------------------------------------------------------------------
    # All-flows check
    # ------------------------------------------------------------------

    def verify_all_flows(self) -> list[CheckResult]:
        """Run consistency checks for every flow in the store."""
        all_flows = self.store.get_all_flows()
        results = []
        for flow in all_flows:
            results.append(self._check_branch(flow["branch"]))
        return results

    # ------------------------------------------------------------------
    # Local auto-fix (current branch, no network)
    # ------------------------------------------------------------------

    def auto_fix(self, issues: list[str]) -> FixResult:
        """Auto-fix local consistency issues for the current branch.

        Handles:
        - Missing shared current.md (creates empty placeholder)

        Network-dependent fixes (missing task_issue_number) require --init.
        """
        branch = self.git_client.get_current_branch()
        fixed: list[str] = []

        for issue in issues:
            if "Shared handoff file not found" in issue:
                git_dir = self.git_client.get_git_common_dir()
                handoff_path = get_branch_handoff_dir(git_dir, branch) / "current.md"
                handoff_path.parent.mkdir(parents=True, exist_ok=True)
                handoff_path.write_text(f"# {branch}\n")
                fixed.append(issue)
                logger.bind(domain="check", action="fix", branch=branch).info(
                    f"Created missing handoff file: {handoff_path}"
                )

        unfixed = [i for i in issues if i not in fixed]
        if unfixed:
            hint = "  Run `vibe check --init` to fix issues requiring remote data."
            return FixResult(
                success=False,
                error="Could not auto-fix:\n"
                + "\n".join(f"  - {i}" for i in unfixed)
                + f"\n{hint}",
            )
        return FixResult(success=True)

    # ------------------------------------------------------------------
    # Remote index init (network, writes task_issue_number)
    # ------------------------------------------------------------------

    def init_remote_index(self, pr_limit: int = 200) -> InitResult:
        """全量扫描远端，回填所有 flow 的 task_issue_number。

        路径 A — merged PR body 解析 Closes/Fixes/Resolves #xxx
        路径 B — GitHub Project items closingIssuesReferences
        已有 task_issue_number 的 flow 跳过（不覆盖）。
        """
        logger.bind(domain="check", action="init_remote_index").info(
            "Building remote index (PR body + GitHub Project items)"
        )
        branch_issue_map = self._build_branch_issue_map(pr_limit)
        return self._backfill_flows(branch_issue_map)

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

    def _backfill_flows(self, branch_issue_map: dict[str, list[int]]) -> InitResult:
        """将 branch_issue_map 回填到本地 store。"""
        all_flows = self.store.get_all_flows()
        updated, skipped, unresolvable = 0, 0, []

        for flow in all_flows:
            branch = flow["branch"]
            if flow.get("task_issue_number"):
                skipped += 1
                continue
            issues_for_branch = branch_issue_map.get(branch, [])
            if not issues_for_branch:
                unresolvable.append(branch)
                continue

            task_issue, extra_issues = issues_for_branch[0], issues_for_branch[1:]
            self.store.update_flow_state(
                branch, task_issue_number=task_issue, latest_actor="check --init"
            )
            self.store.add_issue_link(branch, task_issue, "task")
            self.store.add_event(
                branch,
                "issue_linked",
                "check --init",
                f"Issue #{task_issue} back-filled as task",
            )
            for extra in extra_issues:
                self.store.add_issue_link(branch, extra, "repo")
                self.store.add_event(
                    branch,
                    "issue_linked",
                    "check --init",
                    f"Issue #{extra} back-filled as repo",
                )
            logger.bind(domain="check", branch=branch, task_issue=task_issue).info(
                "Back-filled task_issue_number"
            )
            updated += 1

        return InitResult(
            total_flows=len(all_flows),
            updated=updated,
            skipped=skipped,
            unresolvable=unresolvable,
        )
