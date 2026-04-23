# ruff: noqa: E501
"""Check service implementation for verifying handoff store consistency."""

from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.models.orchestration import IssueState
from vibe3.models.pr import PRState
from vibe3.services.check_remote import (
    CheckRemote,
    is_empty_auto_scene,
    issue_state_from_payload,
    requires_handoff,
    resolve_task_issue_number,
)
from vibe3.services.flow_block_mixin import sync_flow_done_task_label
from vibe3.services.flow_pr_state import evaluate_flow_pr_state
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
    # Core Logic
    # ------------------------------------------------------------------

    def verify_current_flow(self) -> CheckResult:
        """Verify current branch flow consistency."""
        logger.bind(domain="check", action="verify").info("Verifying flow consistency")
        branch = self.git_client.get_current_branch()
        return self._check_branch(branch)

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
        branch_missing = False
        try:
            # Use git branch --list to check only local branches
            output = self.git_client._run(["branch", "--list", branch])
            if not output.strip():
                # Not found locally. Check if it's a safe branch.
                from vibe3.services.flow_service import FlowService

                if not branch.startswith(FlowService.SAFE_BRANCH_PREFIX):
                    branch_missing = True
        except Exception as e:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to verify local branch existence: {e}"
            )

        # task issue exists and is open on GitHub
        issue_links = self.store.get_issue_links(branch)
        task_issue = resolve_task_issue_number(branch, flow_data, issue_links)
        task_issues = [lnk for lnk in issue_links if lnk["issue_role"] == "task"]

        task_issue_closed = False
        orchestration_state: IssueState | None = None
        issue_payload: dict | None = None
        if task_issue:
            issue = self.github_client.view_issue(task_issue)
            if issue == "network_error":
                issues.append(
                    f"Cannot verify task issue #{task_issue}: network/auth error"
                )
            elif not issue:
                issues.append(f"Task issue #{task_issue} not found on GitHub")
            elif isinstance(issue, dict):
                issue_payload = issue
                orchestration_state = issue_state_from_payload(issue)
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
                pr_eval = evaluate_flow_pr_state(pr)
                if pr_eval.can_mark_flow_done:
                    self._mark_flow_done(
                        branch,
                        f"PR #{pr_eval.pr_number} is MERGED (detected from GitHub)",
                        cleanup_local_scene=not branch_missing,
                    )
                    return CheckResult(is_valid=True, branch=branch, issues=[])
                elif pr_eval.is_closed_not_merged:
                    issues.append(
                        f"PR #{pr_eval.pr_number} is CLOSED but not merged — "
                        f"flow cannot auto-complete; consider abandon or manual resolution"
                    )
        except Exception as e:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to verify PR status from GitHub: {e}"
            )
            # Cannot verify PR status when GitHub API fails
            # TODO: Check cache service when implemented to provide offline PR number
            issues.append(f"Cannot verify PR status for branch '{branch}': {e}")

        # Auto-complete when task issue is closed (and no open PR found)
        if task_issue_closed:
            try:
                open_prs = self.github_client.list_prs_for_branch(branch)
                if not open_prs:
                    self._mark_flow_done(
                        branch,
                        f"Task issue #{task_issue} is CLOSED (no open PR found)",
                        cleanup_local_scene=not branch_missing,
                    )
                    return CheckResult(is_valid=True, branch=branch, issues=[])
            except Exception as e:
                logger.bind(domain="check", branch=branch).warning(
                    f"Failed to check for open PRs after task issue closed: {e}"
                )

        flow_status = flow_data.get("flow_status", "active")
        if (
            flow_status == "stale"
            and branch.startswith("task/issue-")
            and orchestration_state == IssueState.READY
        ):
            if self._rebuild_stale_ready_flow(
                branch,
                task_issue=task_issue,
                issue_payload=issue_payload,
            ):
                return CheckResult(is_valid=True, branch=branch, issues=[])

        if branch_missing:
            reason = f"Branch '{branch}' no longer exists locally"
            self._mark_flow_aborted(branch, reason)
            return CheckResult(is_valid=True, branch=branch, issues=[])

        if (
            flow_status == "active"
            and branch.startswith("task/issue-")
            and orchestration_state == IssueState.READY
            and is_empty_auto_scene(flow_data)
            and not self._has_worktree(branch)
        ):
            self._mark_flow_stale(
                branch,
                f"Issue #{task_issue} remains state/ready with no active scene",
            )
            return CheckResult(is_valid=True, branch=branch, issues=[])

        # ref files exist
        if flow_status not in ("done", "aborted", "stale"):
            for ref_field in ["plan_ref", "report_ref", "audit_ref"]:
                ref_value = flow_data.get(ref_field)
                if ref_value and not Path(ref_value).exists():
                    issues.append(f"{ref_field} file not found: {ref_value}")

        # shared current.md
        if flow_status not in ("done", "aborted", "stale") and requires_handoff(
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

    def _cleanup_local_scene(self, branch: str, *, force_delete: bool) -> None:
        """Best-effort cleanup of worktree and local branch for a converged flow."""
        worktree_path = self.git_client.find_worktree_path_for_branch(branch)
        if worktree_path is not None:
            try:
                self.git_client.remove_worktree(worktree_path, force=True)
            except Exception as exc:
                logger.bind(domain="check", branch=branch).warning(
                    f"Failed to remove worktree during local scene cleanup: {exc}"
                )
        try:
            self.git_client.delete_branch(
                branch,
                force=force_delete,
                skip_if_worktree=True,
            )
        except Exception as exc:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to delete branch during local scene cleanup: {exc}"
            )

    def _rebuild_stale_ready_flow(
        self,
        branch: str,
        *,
        task_issue: int | None,
        issue_payload: dict | None,
    ) -> bool:
        """Rebuild stale canonical ready flow as a fresh registered task flow."""
        issue_number = task_issue
        if issue_number is None:
            try:
                issue_number = int(branch.removeprefix("task/issue-"))
            except ValueError:
                return False

        from vibe3.execution.flow_dispatch import FlowManager
        from vibe3.models.orchestra_config import OrchestraConfig
        from vibe3.models.orchestration import IssueInfo

        issue = IssueInfo(
            number=issue_number,
            title=str((issue_payload or {}).get("title") or f"Issue {issue_number}"),
            state=IssueState.READY,
            labels=[IssueState.READY.to_label()],
        )
        manager = FlowManager(
            OrchestraConfig.from_settings(),
            store=self.store,
            git=self.git_client,
            github=self.github_client,
        )
        manager.create_flow_for_issue(issue)
        return True

    def _mark_flow_done(
        self,
        branch: str,
        reason: str,
        *,
        cleanup_local_scene: bool = True,
    ) -> None:
        """Mark a flow as done and record the event."""
        logger.bind(
            domain="check",
            action="auto_complete_flow",
            branch=branch,
        ).info(f"Auto-completing flow: {reason}")
        self.store.update_flow_state(branch, flow_status="done")
        sync_flow_done_task_label(self.store, branch)
        self.store.add_event(
            branch,
            "flow_auto_completed",
            "system",
            f"Flow auto-completed: {reason}",
        )
        if cleanup_local_scene:
            self._cleanup_local_scene(branch, force_delete=True)

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
