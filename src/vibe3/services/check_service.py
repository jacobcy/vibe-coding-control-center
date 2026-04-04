# ruff: noqa: E501
"""Check service implementation for verifying handoff store consistency."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.flow import IssueLink
from vibe3.models.orchestration import IssueState
from vibe3.models.pr import PRState
from vibe3.services.check_remote import CheckRemote
from vibe3.utils.git_helpers import get_branch_handoff_dir


@dataclass
class CheckResult:
    """Result of consistency check for a single branch."""

    is_valid: bool
    issues: list[str]
    branch: str = ""


@dataclass
class FixResult:
    """Result of auto-fix operation."""

    success: bool
    error: str | None = None
    applied: list[str] = field(default_factory=list)


@dataclass
class InitResult:
    """Result of remote index initialization."""

    total_flows: int
    updated: int
    skipped: int
    unresolvable: list[str] = field(default_factory=list)


@dataclass
class ExecuteCheckResult:
    """Result of unified check execution."""

    mode: Literal["default", "init", "all", "fix", "fix_all"]
    success: bool
    summary: str
    details: dict = field(default_factory=dict)


class CheckService(CheckRemote):
    """Service for verifying handoff store consistency and auto-fixing issues."""

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
    # Unified Execution
    # ------------------------------------------------------------------

    def execute_check(
        self,
        mode: Literal["default", "init", "all", "fix", "fix_all"] = "default",
        branch: str | None = None,
    ) -> ExecuteCheckResult:
        """Unified check execution with mode-based routing."""
        if mode == "init":
            return self._handle_init_mode()
        elif mode == "all":
            return self._handle_all_mode()
        elif mode == "fix":
            return self._handle_fix_mode(branch)
        elif mode == "fix_all":
            return self._handle_fix_all_mode()
        else:
            return self._handle_default_mode(branch)

    def _handle_init_mode(self) -> ExecuteCheckResult:
        """Handle --init mode: scan merged PRs to back-fill task_issue_number."""
        result = self.init_remote_index()
        summary = (
            f"Done  total={result.total_flows}  "
            f"updated={result.updated}  skipped={result.skipped}"
        )
        return ExecuteCheckResult(
            mode="init",
            success=True,
            summary=summary,
            details=(
                {"unresolvable": result.unresolvable} if result.unresolvable else {}
            ),
        )

    def _handle_all_mode(self) -> ExecuteCheckResult:
        """Handle --all mode: check active flows."""
        results = self.verify_all_flows(status="active")
        invalid = [r for r in results if not r.is_valid]
        return ExecuteCheckResult(
            mode="all",
            success=len(invalid) == 0,
            summary=(
                f"All {len(results)} active flows passed"
                if not invalid
                else f"{len(invalid)}/{len(results)} active flows have issues"
            ),
            details={"invalid": invalid},
        )

    def _handle_fix_all_mode(self) -> ExecuteCheckResult:
        """Handle --fix --all mode: check active flows and auto-fix fixable issues."""
        results = self.verify_all_flows(status="active")
        invalid = [r for r in results if not r.is_valid]
        if not invalid:
            return ExecuteCheckResult(
                mode="fix_all",
                success=True,
                summary=f"All {len(results)} active flows passed",
            )

        fixed_count = 0
        failed: list[str] = []
        for r in invalid:
            fix_result = self.auto_fix_branch(r.branch, r.issues)
            if fix_result.success:
                fixed_count += 1
            else:
                error_msg = fix_result.error or "unknown error"
                failed.append(f"{r.branch}: {error_msg}")

        total = len(invalid)
        if failed:
            summary = f"Fixed {fixed_count}/{total}, {len(failed)} had unfixable issues"
            return ExecuteCheckResult(
                mode="fix_all",
                success=False,
                summary=summary,
                details={"fixed": fixed_count, "failed": failed},
            )
        summary = (
            f"All {fixed_count} fixable issues resolved across {len(results)} flows"
        )
        return ExecuteCheckResult(
            mode="fix_all",
            success=True,
            summary=summary,
            details={"fixed": fixed_count},
        )

    def _handle_fix_mode(self, branch: str | None) -> ExecuteCheckResult:
        """Handle --fix mode: auto-fix current branch."""
        result_single = self.verify_current_flow()
        if result_single.is_valid:
            return ExecuteCheckResult(
                mode="fix", success=True, summary="All checks passed"
            )

        fix_result = self.auto_fix(result_single.issues, branch=branch)
        return ExecuteCheckResult(
            mode="fix",
            success=fix_result.success,
            summary=(
                "All issues fixed"
                if fix_result.success
                else f"Error: {fix_result.error}"
            ),
            details={"issues": result_single.issues},
        )

    def _handle_default_mode(self, branch: str | None) -> ExecuteCheckResult:
        """Handle default mode: check current branch."""
        result_single = self.verify_current_flow()
        return ExecuteCheckResult(
            mode="default",
            success=result_single.is_valid,
            summary=(
                "All checks passed"
                if result_single.is_valid
                else f"Issues found for branch '{result_single.branch}'"
            ),
            details={"issues": result_single.issues},
        )

    # ------------------------------------------------------------------
    # Core Logic
    # ------------------------------------------------------------------

    def verify_current_flow(self) -> CheckResult:
        """Verify current branch flow consistency."""
        logger.bind(domain="check", action="verify").info("Verifying flow consistency")
        branch = self.git_client.get_current_branch()
        return self._check_branch(branch)

    @staticmethod
    def _issue_state_from_payload(issue: object) -> IssueState | None:
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

    @staticmethod
    def _requires_handoff(issue_state: IssueState | None) -> bool:
        return issue_state in {
            IssueState.CLAIMED,
            IssueState.HANDOFF,
            IssueState.IN_PROGRESS,
            IssueState.REVIEW,
        }

    @staticmethod
    def _resolve_task_issue_number(
        branch: str,
        flow_data: dict[str, object],
        issue_links: list[dict[str, object]],
    ) -> int | None:
        task_issue = flow_data.get("task_issue_number") or IssueLink.resolve_task_number(
            issue_links
        )
        if task_issue:
            return int(task_issue)

        match = re.fullmatch(r"task/issue-(\d+)", branch)
        if match:
            return int(match.group(1))
        return None

    @staticmethod
    def _is_empty_auto_scene(flow_data: dict[str, object]) -> bool:
        markers = (
            "manager_session_id",
            "planner_session_id",
            "executor_session_id",
            "reviewer_session_id",
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

    def _has_worktree(self, branch: str) -> bool:
        try:
            return self.git_client.find_worktree_path_for_branch(branch) is not None
        except Exception:
            return False

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

        # Check if local branch still exists
        try:
            # Use git branch --list to check only local branches
            output = self.git_client._run(["branch", "--list", branch])
            if not output.strip():
                # Not found locally. Check if it's a safe branch.
                from vibe3.services.flow_service import FlowService

                if not branch.startswith(FlowService.SAFE_BRANCH_PREFIX):
                    reason = f"Branch '{branch}' no longer exists locally"
                    self._mark_flow_aborted(branch, reason)
                    return CheckResult(is_valid=True, branch=branch, issues=[])
        except Exception as e:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to verify local branch existence: {e}"
            )

        # task issue exists and is open on GitHub
        issue_links = self.store.get_issue_links(branch)
        task_issue = self._resolve_task_issue_number(branch, flow_data, issue_links)
        task_issues = [lnk for lnk in issue_links if lnk["issue_role"] == "task"]

        task_issue_closed = False
        orchestration_state: IssueState | None = None
        if task_issue:
            issue = self.github_client.view_issue(task_issue)
            if issue == "network_error":
                issues.append(
                    f"Cannot verify task issue #{task_issue}: network/auth error"
                )
            elif not issue:
                issues.append(f"Task issue #{task_issue} not found on GitHub")
            elif isinstance(issue, dict):
                orchestration_state = self._issue_state_from_payload(issue)
                if str(issue.get("state", "")).upper() == "CLOSED":
                    task_issue_closed = True

        # only one task issue per branch
        if len(task_issues) > 1:
            issues.append(f"Multiple task issues for branch '{branch}'")

        # PR verification (Remote-first)
        try:
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
        except Exception as e:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to verify PR status from GitHub: {e}"
            )
            if not flow_data.get("pr_number"):
                issues.append(f"Cannot verify PR status for branch '{branch}': {e}")

        # Auto-complete when task issue is closed (and no open PR found)
        if task_issue_closed:
            try:
                open_prs = self.github_client.list_prs_for_branch(branch)
                if not open_prs:
                    self._mark_flow_done(
                        branch,
                        f"Task issue #{task_issue} is CLOSED (no open PR found)",
                    )
                    return CheckResult(is_valid=True, branch=branch, issues=[])
            except Exception as e:
                logger.bind(domain="check", branch=branch).warning(
                    f"Failed to check for open PRs after task issue closed: {e}"
                )

        if (
            flow_data.get("flow_status", "active") == "active"
            and branch.startswith("task/issue-")
            and orchestration_state == IssueState.READY
            and self._is_empty_auto_scene(flow_data)
            and not self._has_worktree(branch)
        ):
            self._mark_flow_stale(
                branch,
                f"Issue #{task_issue} remains state/ready with no active scene",
            )
            return CheckResult(is_valid=True, branch=branch, issues=[])

        # ref files exist
        flow_status = flow_data.get("flow_status", "active")
        if flow_status not in ("done", "aborted", "stale"):
            for ref_field in ["plan_ref", "report_ref", "audit_ref"]:
                ref_value = flow_data.get(ref_field)
                if ref_value and not Path(ref_value).exists():
                    issues.append(f"{ref_field} file not found: {ref_value}")

        # shared current.md
        if flow_status not in ("done", "aborted", "stale") and self._requires_handoff(
            orchestration_state
        ):
            git_dir = self.git_client.get_git_common_dir()
            handoff_path = get_branch_handoff_dir(git_dir, branch) / "current.md"
            if not handoff_path.exists():
                issues.append(f"Shared handoff file not found: {handoff_path}")

        is_valid = len(issues) == 0
        logger.bind(branch=branch, is_valid=is_valid, issues_count=len(issues)).debug(
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

    def _mark_flow_aborted(self, branch: str, reason: str) -> None:
        """Mark a flow as aborted and record the event."""
        logger.bind(
            domain="check",
            action="auto_abort_flow",
            branch=branch,
        ).info(f"Auto-aborting flow: {reason}")
        self.store.update_flow_state(branch, flow_status="aborted")
        self.store.add_event(
            branch,
            "flow_auto_aborted",
            "system",
            f"Flow auto-aborted: {reason}",
        )

    def _mark_flow_stale(self, branch: str, reason: str) -> None:
        """Mark an empty active flow as stale and record the event."""
        logger.bind(
            domain="check",
            action="auto_stale_flow",
            branch=branch,
        ).info(f"Auto-staling flow: {reason}")
        self.store.update_flow_state(branch, flow_status="stale")
        self.store.add_event(
            branch,
            "flow_auto_staled",
            "system",
            f"Flow auto-staled: {reason}",
        )

    def verify_all_flows(
        self, status: str | list[str] | None = "active"
    ) -> list[CheckResult]:
        """Run consistency checks for flows in the store."""
        all_flows = self.store.get_all_flows()
        if status:
            statuses = [status] if isinstance(status, str) else status
            all_flows = [f for f in all_flows if f.get("flow_status") in statuses]

        results = []
        for flow in all_flows:
            results.append(self._check_branch(flow["branch"]))
        return results

    def auto_fix(self, issues: list[str], *, branch: str | None = None) -> FixResult:
        """Auto-fix local consistency issues for a branch."""
        branch = branch or self.git_client.get_current_branch()
        fixed: list[str] = []

        for issue in issues:
            if "Shared handoff file not found" in issue:
                git_dir = self.git_client.get_git_common_dir()
                handoff_path = get_branch_handoff_dir(git_dir, branch) / "current.md"
                handoff_path.parent.mkdir(parents=True, exist_ok=True)
                handoff_path.write_text(f"# {branch}\n", encoding="utf-8")
                fixed.append(issue)
                logger.bind(domain="check", action="fix", branch=branch).debug(
                    f"Created missing handoff file: {handoff_path}"
                )

        unfixed = [i for i in issues if i not in fixed]
        if unfixed:
            hint = "  Some issues cannot be auto-fixed. Try 'vibe3 check --init' or check manually."
            error = (
                "Could not auto-fix:\n"
                + "\n".join(f"  - {i}" for i in unfixed)
                + f"\n{hint}"
            )
            return FixResult(success=False, error=error)
        return FixResult(success=True, applied=fixed)

    def auto_fix_branch(self, branch: str, issues: list[str]) -> FixResult:
        """Auto-fix issues for a specific branch."""
        return self.auto_fix(issues, branch=branch)
