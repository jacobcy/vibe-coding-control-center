"""Check service implementation."""

from dataclasses import dataclass
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

        # task issue exists and is open on GitHub
        issue_links = self.store.get_issue_links(branch)
        task_issues = [lnk for lnk in issue_links if lnk["issue_role"] == "task"]
        task_issue = (
            task_issues[0]["issue_number"]
            if task_issues
            else flow_data.get("task_issue_number")
        )

        task_issue_closed = False
        if task_issue:
            issue = self.github_client.view_issue(task_issue)
            if issue == "network_error":
                issues.append(
                    f"Cannot verify task issue #{task_issue}: network/auth error"
                )
            elif not issue:
                issues.append(f"Task issue #{task_issue} not found on GitHub")
            elif (
                isinstance(issue, dict)
                and str(issue.get("state", "")).upper() == "CLOSED"
            ):
                task_issue_closed = True

        # only one task issue per branch
        if len(task_issues) > 1:
            issues.append(f"Multiple task issues for branch '{branch}'")

        # PR verification (Remote-first)
        # We no longer rely on local pr_number cache; always check GitHub truth.
        prs = self.github_client.list_prs_for_branch(branch)
        if not prs:
            # Check merged/closed to catch stale flows
            all_prs = self.github_client.list_prs_for_branch(branch, state="all")
            prs = [p for p in all_prs if p.state != PRState.OPEN]

        if prs:
            pr = prs[0]
            # Check if PR is closed or merged - auto-complete flow
            if pr.state in (PRState.CLOSED, PRState.MERGED) or pr.merged_at:
                self._mark_flow_done(
                    branch,
                    f"PR #{pr.number} is {pr.state.value} (detected from GitHub)",
                )
                return CheckResult(is_valid=True, branch=branch, issues=[])

        # Auto-complete when task issue is closed (and no open PR found)
        if task_issue_closed:
            open_prs = self.github_client.list_prs_for_branch(branch)
            if not open_prs:
                self._mark_flow_done(
                    branch,
                    f"Task issue #{task_issue} is CLOSED (no open PR found)",
                )
                return CheckResult(is_valid=True, branch=branch, issues=[])

        # ref files exist (skip for terminal flows — artifacts may be cleaned up)
        flow_status = flow_data.get("flow_status", "active")
        if flow_status not in ("done", "aborted", "stale"):
            for ref_field in ["plan_ref", "report_ref", "audit_ref"]:
                ref_value = flow_data.get(ref_field)
                if ref_value and not Path(ref_value).exists():
                    issues.append(f"{ref_field} file not found: {ref_value}")

        # shared current.md (skip for terminal flows)
        if flow_status not in ("done", "aborted", "stale"):
            git_dir = self.git_client.get_git_common_dir()
            handoff_path = get_branch_handoff_dir(git_dir, branch) / "current.md"
            if not handoff_path.exists():
                issues.append(f"Shared handoff file not found: {handoff_path}")

        is_valid = len(issues) == 0
        logger.bind(branch=branch, is_valid=is_valid, issues_count=len(issues)).info(
            "Check completed"
        )
        return CheckResult(is_valid=is_valid, issues=issues, branch=branch)

    def _mark_flow_done(self, branch: str, reason: str) -> None:
        """Mark a flow as done and record the event."""
        logger.bind(
            domain="check",
            action="auto_complete_flow",
            branch=branch,
        ).info(f"Auto-completing flow: {reason}")
        self.store.update_flow_state(branch, flow_status="done")
        self.store.add_event(
            branch,
            "flow_auto_completed",
            "system",
            f"Flow auto-completed: {reason}",
        )

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
                    # No longer backfill pr_number to SQLite
                    self.store.add_event(
                        branch,
                        "pr_verified",
                        "check --fix",
                        f"PR #{pr_number} verified on GitHub (truth only)",
                    )
                    fixed.append(issue)
                    logger.bind(
                        domain="check", action="fix", branch=branch, pr_number=pr_number
                    ).info("PR verified on GitHub (remote-first)")
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
