"""Check service implementation."""

from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.pr import PRState
from vibe3.services.check_execute_mixin import CheckExecuteMixin
from vibe3.services.check_remote_index_mixin import CheckRemoteIndexMixin
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


class CheckService(CheckRemoteIndexMixin, CheckExecuteMixin):
    """Service for verifying handoff store consistency."""

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        github_client: GitHubClient | None = None,
    ) -> None:
        super().__init__(store=store, github_client=github_client)
        self.git_client = git_client or GitClient()

    # ------------------------------------------------------------------
    # Single-branch check
    # ------------------------------------------------------------------

    def verify_current_flow(self) -> CheckResult:
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
            if issue == "network_error":
                issues.append(
                    f"Cannot verify task issue #{task_issue}: network/auth error"
                )
            elif not issue:
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

            # Check if PR is closed or merged - auto-complete flow
            if pr and (pr.state in (PRState.CLOSED, PRState.MERGED) or pr.merged_at):
                logger.bind(
                    domain="check",
                    action="auto_complete_flow",
                    branch=branch,
                    pr_number=pr_number,
                    pr_state=pr.state.value,
                ).info("PR closed/merged, marking flow as done")

                # Mark flow as done
                self.store.update_flow_state(branch, flow_status="done")
                self.store.add_event(
                    branch,
                    "flow_auto_completed",
                    "system",
                    f"Flow auto-completed: PR #{pr_number} is {pr.state.value}",
                )
                issues.append(
                    f"ℹ️ Flow marked as done: PR #{pr_number} is {pr.state.value}"
                )

        # Check for missing PR (branch has PR but database doesn't record it)
        if not pr_number:
            prs = self.github_client.list_prs_for_branch(branch)
            if prs:
                pr_num = prs[0].number
                issues.append(
                    f"Branch has open PR #{pr_num} but database missing pr_number"
                )

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

    def auto_fix(self, issues: list[str], *, branch: str | None = None) -> FixResult:
        """Auto-fix local consistency issues for a branch.

        Handles:
        - Missing shared current.md (creates empty placeholder)
        - Missing pr_number (queries GitHub and updates database)

        Some fixes require network access to GitHub.
        """
        branch = branch or self.git_client.get_current_branch()
        fixed: list[str] = []

        for issue in issues:
            # Fix missing handoff file
            if "Shared handoff file not found" in issue:
                git_dir = self.git_client.get_git_common_dir()
                handoff_path = get_branch_handoff_dir(git_dir, branch) / "current.md"
                handoff_path.parent.mkdir(parents=True, exist_ok=True)
                handoff_path.write_text(f"# {branch}\n")
                fixed.append(issue)
                logger.bind(domain="check", action="fix", branch=branch).info(
                    f"Created missing handoff file: {handoff_path}"
                )

            # Fix missing pr_number
            elif "database missing pr_number" in issue:
                prs = self.github_client.list_prs_for_branch(branch)
                if prs:
                    pr_number = prs[0].number
                    self.store.update_flow_state(
                        branch, pr_number=pr_number, latest_actor="check --fix"
                    )
                    self.store.add_event(
                        branch,
                        "pr_linked",
                        "check --fix",
                        f"PR #{pr_number} linked to flow",
                    )
                    fixed.append(issue)
                    logger.bind(
                        domain="check", action="fix", branch=branch, pr_number=pr_number
                    ).info("Back-filled pr_number")
                else:
                    logger.bind(domain="check", branch=branch).warning(
                        "PR not found on GitHub, cannot fix"
                    )

        unfixed = [i for i in issues if i not in fixed]
        if unfixed:
            hint = (
                "  Some issues cannot be auto-fixed. "
                "Try 'vibe3 check --init' or check manually."
            )
            return FixResult(
                success=False,
                error="Could not auto-fix:\n"
                + "\n".join(f"  - {i}" for i in unfixed)
                + f"\n{hint}",
            )
        return FixResult(success=True)

    def auto_fix_branch(self, branch: str, issues: list[str]) -> FixResult:
        """Auto-fix issues for a specific branch.

        Delegates to auto_fix with explicit branch parameter.
        """
        return self.auto_fix(issues, branch=branch)

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
        updated, skipped, unresolvable = self._backfill_flows(branch_issue_map)
        return InitResult(
            total_flows=len(self.store.get_all_flows()),
            updated=updated,
            skipped=skipped,
            unresolvable=unresolvable,
        )
