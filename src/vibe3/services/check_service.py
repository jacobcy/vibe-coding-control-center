# ruff: noqa: E501
"""Check service implementation for verifying handoff store consistency."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.models.orchestration import IssueState
from vibe3.models.pr import PRState
from vibe3.services.check_remote import (
    CheckRemote,
    is_empty_auto_scene,
    issue_state_from_payload,
    requires_handoff,
    resolve_task_issue_number,
)
from vibe3.utils.git_helpers import get_branch_handoff_dir

if TYPE_CHECKING:
    from vibe3.models.pr import PRResponse


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

    # Terminal flow statuses that indicate completed flows
    TERMINAL_FLOW_STATUSES = ("done", "aborted", "merged")
    # Flow statuses that should be skipped for handoff/ref checks
    INACTIVE_FLOW_STATUSES = ("done", "aborted", "stale")

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        github_client: GitHubClient | None = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()
        self._branch_to_pr: dict[str, PRResponse] = {}

    def _initialize_pr_cache(self) -> None:
        """Initialize PR cache with batch fetch (1 API call instead of N).

        Safe to call multiple times - only fetches once.
        """
        if self._branch_to_pr:
            return  # Already initialized
        try:
            all_prs = self.github_client.list_all_prs(state="all")
            self._branch_to_pr = {pr.head_branch: pr for pr in all_prs}
        except (OSError, ValueError) as exc:
            # OSError: subprocess/gh CLI failures
            # ValueError: JSON parsing errors
            logger.bind(domain="check").warning(f"Failed to fetch PRs: {exc}")
            self._branch_to_pr = {}

    # ------------------------------------------------------------------
    # Core Logic
    # ------------------------------------------------------------------

    def verify_current_flow(self) -> CheckResult:
        """Verify current branch flow consistency."""
        logger.bind(domain="check", action="verify").info("Verifying flow consistency")
        branch = self.git_client.get_current_branch()

        # Batch fetch all PRs (optimization: 1 call instead of N)
        self._initialize_pr_cache()

        return self._check_branch(branch)

    def _has_worktree(self, branch: str) -> bool:
        try:
            return self.git_client.find_worktree_path_for_branch(branch) is not None
        except Exception:
            return False

    def _has_local_branch(self, branch: str) -> bool:
        """Check if local branch exists."""
        try:
            output = self.git_client._run(["branch", "--list", branch])
            return bool(output.strip())
        except Exception:
            return False

    def _has_remote_branch(self, branch: str) -> bool:
        """Check if remote branch exists."""
        try:
            remote_output = self.git_client._run(
                ["branch", "-r", "--list", f"origin/{branch}"]
            )
            return bool(remote_output.strip())
        except Exception:
            return False

    def _check_branch_resources(self, branch: str) -> tuple[bool, bool, bool]:
        """Check if branch has local, remote, and worktree resources.

        Returns:
            Tuple of (has_local, has_remote, has_worktree)
        """
        return (
            self._has_local_branch(branch),
            self._has_remote_branch(branch),
            self._has_worktree(branch),
        )

    def _handle_closed_pr(self, branch: str, pr: "PRResponse") -> CheckResult | None:
        """Handle closed/merged PR by marking flow done.

        Returns CheckResult if PR is closed/merged, None otherwise.
        """
        if pr.state not in (PRState.CLOSED, PRState.MERGED) and not pr.merged_at:
            return None

        suggestions = self._mark_flow_done(
            branch,
            f"PR #{pr.number} is {pr.state.value} (detected from GitHub)",
        )
        self._update_pr_cache(branch, pr)

        result_issues: list[str] = []
        if suggestions.get("issue_to_close"):
            result_issues.append(
                f"Suggestion: Issue #{suggestions['issue_to_close']} is still OPEN. "
                "Consider closing it."
            )
        return CheckResult(is_valid=True, branch=branch, issues=result_issues)

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

        # PR verification (Remote-first) - use cached PR data
        pr = self._branch_to_pr.get(branch)
        if pr:
            result = self._handle_closed_pr(branch, pr)
            if result:
                return result
        else:
            # No PR found in cache, try API as fallback
            try:
                prs = self.github_client.list_prs_for_branch(branch)
                if not prs:
                    # Check merged/closed to catch stale flows
                    all_prs = self.github_client.list_prs_for_branch(
                        branch, state="all"
                    )
                    prs = [p for p in all_prs if p.state != PRState.OPEN]

                if prs:
                    result = self._handle_closed_pr(branch, prs[0])
                    if result:
                        return result
            except Exception as e:
                logger.bind(domain="check", branch=branch).warning(
                    f"Failed to verify PR status from GitHub: {e}"
                )
                issues.append(f"Cannot verify PR status for branch '{branch}': {e}")

        # Auto-abort when task issue is closed (no open PR found)
        # Semantic: Issue closed without PR = task cancelled/aborted
        cached_pr = self._branch_to_pr.get(branch)
        if task_issue_closed and (not cached_pr or cached_pr.state != PRState.OPEN):
            self._mark_flow_aborted(
                branch, f"Task issue #{task_issue} is CLOSED (no open PR found)"
            )
            return CheckResult(is_valid=True, branch=branch, issues=[])

        flow_status = flow_data.get("flow_status", "active")

        # Handle stale ready flow rebuild
        if (
            flow_status == "stale"
            and branch.startswith("task/issue-")
            and orchestration_state == IssueState.READY
            and self._rebuild_stale_ready_flow(
                branch, task_issue=task_issue, issue_payload=issue_payload
            )
        ):
            return CheckResult(is_valid=True, branch=branch, issues=[])

        # Handle missing local branch
        if branch_missing:
            self._mark_flow_aborted(
                branch, f"Branch '{branch}' no longer exists locally"
            )
            return CheckResult(is_valid=True, branch=branch, issues=[])

        # Handle empty active ready flow
        if (
            flow_status == "active"
            and branch.startswith("task/issue-")
            and orchestration_state == IssueState.READY
            and is_empty_auto_scene(flow_data)
            and not self._has_worktree(branch)
        ):
            self._mark_flow_stale(
                branch, f"Issue #{task_issue} remains state/ready with no active scene"
            )
            return CheckResult(is_valid=True, branch=branch, issues=[])

        # ref files exist
        if flow_status not in self.INACTIVE_FLOW_STATUSES:
            for ref_field in ["plan_ref", "report_ref", "audit_ref"]:
                ref_value = flow_data.get(ref_field)
                if ref_value:
                    # Resolve path relative to the flow's worktree, not current worktree
                    from vibe3.utils.path_helpers import resolve_ref_path

                    worktree_path = self.git_client.find_worktree_path_for_branch(
                        branch
                    )
                    resolved_path = resolve_ref_path(
                        ref_value,
                        worktree_root=str(worktree_path) if worktree_path else None,
                        absolute=True,
                    )
                    if resolved_path and not Path(resolved_path).exists():
                        # Provide actionable suggestion for damaged flow
                        issues.append(
                            f"{ref_field} file not found: {ref_value}. "
                            f"Suggestion: Run 'vibe3 task resume --blocked {task_issue}' to reset."
                        )

        # shared current.md
        if flow_status not in self.INACTIVE_FLOW_STATUSES and requires_handoff(
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
        """Best-effort cleanup of worktree, local branch, and remote branch.

        Checks existence before attempting deletion to avoid noisy warnings.
        Uses extracted helper methods for consistency.
        """
        # 1. Clean up worktree
        if self._has_worktree(branch):
            try:
                worktree_path = self.git_client.find_worktree_path_for_branch(branch)
                if worktree_path:
                    self.git_client.remove_worktree(worktree_path, force=True)
            except Exception as exc:
                logger.bind(domain="check", branch=branch).warning(
                    f"Failed to remove worktree during local scene cleanup: {exc}"
                )

        # 2. Clean up local branch
        if self._has_local_branch(branch):
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

        # 3. Clean up remote branch
        if self._has_remote_branch(branch):
            try:
                self.git_client.delete_remote_branch(branch)
            except Exception as exc:
                logger.bind(domain="check", branch=branch).warning(
                    f"Failed to delete remote branch during local scene cleanup: {exc}"
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
        from vibe3.models.orchestration import IssueInfo

        issue = IssueInfo(
            number=issue_number,
            title=str((issue_payload or {}).get("title") or f"Issue {issue_number}"),
            state=IssueState.READY,
            labels=[IssueState.READY.to_label()],
        )
        manager = FlowManager(
            load_orchestra_config(),
            store=self.store,
            git=self.git_client,
            github=self.github_client,
        )
        manager.create_flow_for_issue(issue)
        return True

    def _mark_flow_status(
        self,
        branch: str,
        status: str,
        reason: str,
        event_type: str,
        action: str,
    ) -> None:
        """Generic method to mark flow status and record event."""
        logger.bind(
            domain="check",
            action=action,
            branch=branch,
        ).info(f"{action}: {reason}")
        self.store.update_flow_state(branch, flow_status=status)
        self.store.add_event(
            branch,
            event_type,
            "system",
            f"Flow auto-{status}: {reason}",
        )

    def _mark_flow_done(
        self,
        branch: str,
        reason: str,
    ) -> dict[str, int | None]:
        """Mark a flow as done and record the event.

        Note: Branch cleanup is deferred to 'vibe3 check --clean-branch'.
        This keeps check fast and allows code reuse.

        Returns:
            Dict with suggestions, e.g., {"issue_to_close": 123}
        """
        # Auto-save baseline snapshot on flow auto-complete
        try:
            from vibe3.analysis import snapshot_service

            snapshot_service.save_branch_baseline(branch)
        except Exception as e:
            logger.warning(f"Failed to save branch baseline on auto-complete: {e}")

        self._mark_flow_status(
            branch, "done", reason, "flow_auto_completed", "auto_complete_flow"
        )

        # Check if linked issue is still open
        suggestions: dict[str, int | None] = {"issue_to_close": None}
        issue_links = self.store.get_issue_links(branch)
        task_issues = [lnk for lnk in issue_links if lnk["issue_role"] == "task"]
        if task_issues:
            task_issue = task_issues[0]["issue_number"]
            issue = self.github_client.view_issue(task_issue)
            # view_issue() can return dict, None, or "network_error" string
            if (
                issue
                and isinstance(issue, dict)
                and str(issue.get("state", "")).upper() != "CLOSED"
            ):
                suggestions["issue_to_close"] = task_issue

        return suggestions

    def _mark_flow_aborted(self, branch: str, reason: str) -> None:
        """Mark a flow as aborted and record the event."""
        self._mark_flow_status(
            branch, "aborted", reason, "flow_auto_aborted", "auto_abort_flow"
        )

    def _mark_flow_stale(self, branch: str, reason: str) -> None:
        """Mark an empty active flow as stale and record the event."""
        self._mark_flow_status(
            branch, "stale", reason, "flow_auto_staled", "auto_stale_flow"
        )

    def verify_all_flows(
        self, status: str | list[str] | None = "active"
    ) -> list[CheckResult]:
        """Run consistency checks for flows in the store."""
        # Initialize PR cache (optimization: 1 API call instead of N)
        self._initialize_pr_cache()

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

    def _update_pr_cache(self, branch: str, pr: "PRResponse") -> None:
        """Update PR cache when check discovers changes.

        This is a write operation: check command updates cache
        when it discovers PR state changes.

        Args:
            branch: Branch name
            pr: PR response object with title and number
        """
        try:
            from vibe3.services.issue_title_cache_service import IssueTitleCacheService

            title_cache = IssueTitleCacheService(self.store, self.github_client)
            title_cache.update_pr(
                branch=branch,
                pr_number=pr.number,
                pr_title=pr.title,
            )
            logger.bind(domain="check", branch=branch).info(
                f"Updated PR cache: #{pr.number} - {pr.title}"
            )
        except Exception as e:
            logger.bind(domain="check", branch=branch).warning(
                f"Failed to update PR cache: {e}"
            )

    def clean_residual_branches(self) -> dict[str, object]:
        """Check and clean residual branches for terminal flows.

        Flows marked as done/aborted/merged should have their resources cleaned:
        - Worktree removed
        - Local/remote branches deleted
        - Handoff files cleared
        - Flow record deleted from database

        This allows issues to be cleanly re-dispatched if they are still open.

        Returns:
            Dict with summary and details of cleaned branches.
        """
        from vibe3.services.flow_cleanup_service import FlowCleanupService

        logger.bind(domain="check", action="clean_residual").info(
            "Checking for residual branches"
        )

        # Get all terminal flows (done/aborted/merged)
        all_flows = self.store.get_all_flows()
        terminal_flows = [
            f for f in all_flows if f.get("flow_status") in self.TERMINAL_FLOW_STATUSES
        ]

        cleanup_service = FlowCleanupService(
            git_client=self.git_client,
            store=self.store,
        )

        cleaned: list[str] = []
        removed_invalid: list[str] = []
        failed: list[str] = []

        for flow in terminal_flows:
            branch = flow["branch"]

            # Remove invalid branch records (e.g., HEAD)
            if branch == "HEAD" or branch.startswith("HEAD"):
                try:
                    self.store.delete_flow(branch)
                    removed_invalid.append(branch)
                    logger.bind(domain="check", branch=branch).info(
                        "Removed invalid flow record"
                    )
                except Exception as exc:
                    logger.bind(domain="check", branch=branch).warning(
                        f"Failed to remove invalid flow record: {exc}"
                    )
                continue

            # Use unified cleanup service for all terminal flows
            try:
                results = cleanup_service.cleanup_flow_scene(
                    branch,
                    include_remote=True,
                    terminate_sessions=True,
                )

                # Consider cleanup successful if flow record was deleted
                if results.get("flow_record", False):
                    cleaned.append(branch)
                    logger.bind(domain="check", branch=branch).info(
                        "Cleaned terminal flow resources"
                    )
                else:
                    failed.append(f"{branch}: flow record deletion failed")
            except Exception as exc:
                failed.append(f"{branch}: {exc}")
                logger.bind(domain="check", branch=branch).warning(
                    f"Failed to clean terminal flow resources: {exc}"
                )

        summary = f"Cleaned {len(cleaned)} terminal flows"
        if removed_invalid:
            summary += f", removed {len(removed_invalid)} invalid records"
        if failed:
            summary += f", failed {len(failed)}"

        return {
            "summary": summary,
            "cleaned": cleaned,
            "removed_invalid": removed_invalid,
            "failed": failed,
            "total_flows_checked": len(terminal_flows),
        }
