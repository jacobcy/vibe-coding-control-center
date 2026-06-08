"""Check service implementation for verifying handoff store consistency."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from loguru import logger

from vibe3.clients import GitClient, GitHubClient, GitHubClientProtocol, SQLiteClient
from vibe3.config import VibeConfig
from vibe3.models import IssueState
from vibe3.services.check_lock import check_lock
from vibe3.services.check_pr_service import CheckPRService
from vibe3.services.check_remote import (
    CheckRemote,
    is_empty_auto_scene,
    issue_state_from_payload,
)
from vibe3.services.flow_status_service import FlowStatusService
from vibe3.services.pr.service import PRService

if TYPE_CHECKING:
    from vibe3.models import PRResponse


@dataclass
class CheckResult:
    """Result of consistency check for a single branch."""

    is_valid: bool
    issues: list[str]
    warnings: list[str] = field(default_factory=list)
    branch: str = ""


@dataclass
class FixResult:
    """Result of auto-fix operation."""

    success: bool
    error: str | None = None
    applied: list[str] = field(default_factory=list)


class CheckService(CheckRemote):
    """Service for verifying handoff store consistency and auto-fixing issues."""

    # Flow statuses that should be skipped for handoff/ref checks
    INACTIVE_FLOW_STATUSES = ("done", "aborted", "stale")
    # Threshold for orphaned flow detection (commits behind main)
    ORPHAN_FLOW_BEHIND_THRESHOLD = 100

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClient | None = None,
        github_client: GitHubClient | None = None,
        flow_status_service: FlowStatusService | None = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.github_client = github_client or GitHubClient()
        self._flow_status_service = flow_status_service or FlowStatusService(
            store=self.store,
            git_client=self.git_client,
            github_client=self.github_client,
        )
        self._pr_service = PRService(
            github_client=cast(GitHubClientProtocol, self.github_client),
            git_client=self.git_client,
            store=self.store,
        )
        self._check_pr_service = CheckPRService(
            store=self.store,
            git_client=self.git_client,
            github_client=self.github_client,
            flow_status_service=self._flow_status_service,
        )
        self._branch_to_pr: dict[str, PRResponse] = {}
        # Load config for protected branches
        self._vibe_config = VibeConfig()

    @property
    def protected_branches(self) -> set[str]:
        """Get protected branches from config (main, master, develop, etc.)."""
        return set(self._vibe_config.flow.protected_branches)

    def _initialize_pr_cache(self) -> None:
        """Initialize PR cache with batch fetch (1 API call instead of N).

        Safe to call multiple times - only fetches once.
        """
        if self._branch_to_pr:
            return  # Already initialized
        try:
            self._branch_to_pr = self._pr_service.refresh_recent_pr_cache()
        except (OSError, ValueError) as exc:
            # OSError: subprocess/gh CLI failures
            # ValueError: JSON parsing errors
            logger.bind(domain="check").warning(f"Failed to fetch PRs: {exc}")
            self._branch_to_pr = {}

    def invalidate_pr_cache(self) -> None:
        """Invalidate PR cache to force refresh on next check.

        Clears the cached PR data so that the next health check
        will fetch fresh PR state from GitHub API.
        """
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

    def verify_branch(self, branch: str) -> CheckResult:
        """Verify a specific branch flow consistency.

        Args:
            branch: Branch name to verify.

        Returns:
            CheckResult with validation status and issues.
        """
        # Validate branch is not protected or remote
        if branch in self.protected_branches or branch.startswith("origin/"):
            return CheckResult(
                is_valid=False,
                issues=[f"Branch '{branch}' is a protected or remote branch"],
                branch=branch,
            )

        # Batch fetch all PRs (optimization: 1 call instead of N)
        self._initialize_pr_cache()

        return self._check_branch(branch)

    def _has_worktree(self, branch: str) -> bool:
        try:
            return self.git_client.find_worktree_path_for_branch(branch) is not None
        except Exception:
            return False

    def _count_commits_behind_main(self, branch: str) -> int | None:
        """Count how many commits the branch is behind origin/main.

        Returns None if cannot determine (e.g., no common ancestor).
        """
        try:
            # Fetch origin/main to get latest
            self.git_client._run(["fetch", "origin", "main", "--quiet"])
            # Count commits in origin/main not in branch
            output = self.git_client._run(
                ["rev-list", "--count", f"{branch}..origin/main"]
            )
            return int(output.strip()) if output.strip() else None
        except Exception:
            return None

    def _check_multiple_state_labels(
        self, issue_number: int, issue_payload: dict
    ) -> tuple[list[str], list[str], IssueState | None]:
        """Check for multiple state/* labels and auto-fix the anomaly.

        An issue should have exactly one state/* label. Having multiple
        (e.g., state/blocked + state/review) is an anomaly that needs
        correction. This method detects the anomaly and uses LabelService
        to atomically fix it by keeping the highest-priority state.

        Priority: blocked > done > in-progress > review > merge-ready >
        handoff > claimed > ready

        If none of the known IssueState labels are present (e.g., a future/new
        state/* label), the issue is flagged for manual fix instead of forcing
        a default state.

        Returns:
            Tuple of (warnings, issues). Warnings for successful auto-fix,
            issues for cases requiring manual intervention.
        """
        labels = issue_payload.get("labels", [])
        state_labels = [
            lbl["name"]
            for lbl in labels
            if isinstance(lbl, dict) and lbl.get("name", "").startswith("state/")
        ]

        if len(state_labels) <= 1:
            return ([], [], None)

        # Determine which state to keep (highest priority)
        priority_order = [
            IssueState.BLOCKED,
            IssueState.DONE,
            IssueState.IN_PROGRESS,
            IssueState.REVIEW,
            IssueState.MERGE_READY,
            IssueState.HANDOFF,
            IssueState.CLAIMED,
            IssueState.READY,
        ]

        # Find the highest priority state from existing labels
        target_state = None
        for candidate in priority_order:
            if candidate.to_label() in state_labels:
                target_state = candidate
                break

        # If no known IssueState found, flag for manual fix
        if target_state is None:
            logger.bind(domain="check", action="fix").warning(
                f"Issue #{issue_number} has multiple state labels with "
                f"unknown states: {state_labels}"
            )
            return (
                [],
                [
                    f"Issue #{issue_number} has multiple state labels "
                    f"({', '.join(state_labels)}) with unknown state, "
                    f"manual fix required"
                ],
                None,
            )

        # Auto-fix using LabelService (atomic: add new, remove old)
        try:
            from vibe3.services.label_service import LabelService

            label_service = LabelService()
            label_service.set_state(issue_number, target_state)
            logger.bind(domain="check", action="fix").info(
                f"Auto-fixed multi-label on issue #{issue_number}: "
                f"{state_labels} -> {target_state.to_label()}"
            )
            return (
                [
                    f"Issue #{issue_number} had multiple state labels "
                    f"({', '.join(state_labels)}), auto-fixed to "
                    f"{target_state.to_label()}"
                ],
                [],
                target_state,
            )
        except Exception as exc:
            logger.bind(domain="check", action="fix").warning(
                f"Failed to auto-fix multi-label on issue " f"#{issue_number}: {exc}"
            )
            return (
                [],
                [
                    f"Issue #{issue_number} has multiple state labels "
                    f"({', '.join(state_labels)}), manual fix required"
                ],
                None,
            )

    def _check_branch(self, branch: str) -> CheckResult:
        """Run all consistency checks for a single branch."""
        # Acquire branch-level lock to prevent concurrent checks
        with check_lock(branch, self.git_client) as acquired:
            if not acquired:
                return CheckResult(
                    is_valid=False,
                    issues=[
                        f"Check skipped for '{branch}' (lock held by another process)"
                    ],
                    branch=branch,
                )

            issues: list[str] = []
            warnings: list[str] = []

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
            from vibe3.services.issue.flow import IssueFlowService

            issue_flow_service = IssueFlowService(store=self.store)
            task_issue = issue_flow_service.resolve_task_issue_number(branch)
            issue_links = self.store.get_issue_links(branch)
            task_issues = [lnk for lnk in issue_links if lnk["issue_role"] == "task"]

            task_issue_closed = False
            orchestration_state: IssueState | None = None
            issue_payload: dict | None = None
            if task_issue:
                from vibe3.clients.github_field_constants import (
                    GITHUB_DEFAULT_VIEW_FIELDS,
                )

                # Need state, labels, and body for state validation
                issue = self.github_client.view_issue(
                    task_issue, fields=list(GITHUB_DEFAULT_VIEW_FIELDS)
                )
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

                    # Check for multiple state/* labels (anomaly)
                    label_warnings, label_issues, fixed_state = (
                        self._check_multiple_state_labels(task_issue, issue_payload)
                    )
                    warnings.extend(label_warnings)
                    issues.extend(label_issues)
                    if fixed_state is not None:
                        orchestration_state = fixed_state

            # only one task issue per branch
            if len(task_issues) > 1:
                issues.append(f"Multiple task issues for branch '{branch}'")

            # ==== PR State Handling ====
            # Priority 1: Handle PR state changes (merged/closed)
            pr = self._branch_to_pr.get(branch)
            if pr:
                handled, pr_issues, pr_warnings = (
                    self._check_pr_service.handle_pr_terminal_state(branch, pr)
                )
                if handled:
                    return CheckResult(
                        is_valid=len(pr_issues) == 0,
                        issues=pr_issues,
                        warnings=pr_warnings,
                        branch=branch,
                    )
            else:
                # No PR found in recent cache; ask PRService for branch status
                try:
                    cached_or_remote_pr = self._pr_service.get_branch_pr_status(branch)
                    if cached_or_remote_pr:
                        handled, pr_issues, pr_warnings = (
                            self._check_pr_service.handle_pr_terminal_state(
                                branch, cached_or_remote_pr
                            )
                        )
                        if handled:
                            return CheckResult(
                                is_valid=len(pr_issues) == 0,
                                issues=pr_issues,
                                warnings=pr_warnings,
                                branch=branch,
                            )
                        self._branch_to_pr[branch] = cached_or_remote_pr
                except Exception as e:
                    logger.bind(domain="check", branch=branch).warning(
                        f"Failed to verify PR status from GitHub: {e}"
                    )
                    issues.append(f"Cannot verify PR status for branch '{branch}': {e}")

            # ==== Issue & Flow State Validation ====
            # Priority 2: Check issue state against flow state
            flow_status = flow_data.get("flow_status", "active")
            is_active_flow = flow_status not in self.INACTIVE_FLOW_STATUSES

            if task_issue_closed:
                if is_active_flow:
                    # Active flow with closed issue and no open PR = anomaly
                    return CheckResult(
                        is_valid=False,
                        branch=branch,
                        issues=[
                            f"Task issue #{task_issue} is CLOSED (no open PR found)"
                        ],
                    )
                # Inactive flow with closed issue = expected terminal state, continue

            # Priority 3: Sync stale blocked state from remote
            # If flow is locally blocked but remote state/blocked was removed,
            # clear the stale local state so the flow is not permanently stuck.
            if (
                flow_status == "blocked"
                and task_issue
                and orchestration_state is not None
                and orchestration_state != IssueState.BLOCKED
            ):
                self._flow_status_service.mark_flow_unblocked(
                    branch, "Remote state/blocked label removed"
                )
                return CheckResult(is_valid=True, branch=branch, issues=[])

            # Handle stale ready flow rebuild
            if (
                flow_status == "stale"
                and branch.startswith("task/issue-")
                and orchestration_state == IssueState.READY
                and self._flow_status_service.rebuild_stale_ready_flow(
                    branch, task_issue=task_issue, issue_payload=issue_payload
                )
            ):
                return CheckResult(is_valid=True, branch=branch, issues=[])

            # Handle missing local branch
            if branch_missing:
                self._flow_status_service.mark_flow_aborted(
                    branch, f"Branch '{branch}' no longer exists locally"
                )
                return CheckResult(
                    is_valid=False,
                    branch=branch,
                    issues=[f"Branch '{branch}' no longer exists locally"],
                )

                # Handle orphaned active flow: no task issue + no worktree + stale
            # Only clean up flows that have no issue binding and are
            # significantly behind
            if (
                flow_status == "active"
                and not task_issue
                and not self._has_worktree(branch)
            ):
                try:
                    behind_count = self._count_commits_behind_main(branch)
                    if (
                        behind_count
                        and behind_count > self.ORPHAN_FLOW_BEHIND_THRESHOLD
                    ):
                        self._flow_status_service.mark_flow_aborted(
                            branch,
                            f"Orphaned flow '{branch}' is {behind_count} "
                            "commits behind main",
                        )
                        return CheckResult(
                            is_valid=False,
                            branch=branch,
                            issues=[
                                f"Orphaned flow '{branch}' is {behind_count} "
                                "commits behind main"
                            ],
                        )
                except Exception as exc:
                    logger.bind(domain="check", branch=branch).debug(
                        f"Could not count commits behind main: {exc}"
                    )

            # Handle empty active ready flow
            if (
                flow_status == "active"
                and branch.startswith("task/issue-")
                and orchestration_state == IssueState.READY
                and is_empty_auto_scene(flow_data)
                and not self._has_worktree(branch)
            ):
                self._flow_status_service.mark_flow_stale(
                    branch,
                    f"Issue #{task_issue} remains state/ready with no active scene",
                )
                return CheckResult(is_valid=True, branch=branch, issues=[])

            # Flow consistency check and auto-recovery
            if flow_status not in self.INACTIVE_FLOW_STATUSES:
                from vibe3.services.flow_recovery_service import (
                    FlowRecoveryService,
                    RecoveryAction,
                )

                recovery_svc = FlowRecoveryService(
                    store=self.store,
                    git_client=self.git_client,
                    github_client=self.github_client,
                )
                action, consistency = recovery_svc.classify(branch)

                if action != RecoveryAction.RESUME_ONLY:
                    # Use precomputed consistency result for error message
                    consistency_error = (
                        consistency.reason if consistency else "No flow record"
                    )

                    try:
                        result = recovery_svc.recover(
                            branch=branch,
                            issue_number=task_issue or 0,
                            reason="Health check auto-recover",
                            auto=True,
                            ensure_worktree=True,
                        )
                        logger.info(
                            "Auto-recovered inconsistent flow",
                            branch=branch,
                            action=result.action.value,
                            detail=result.detail,
                        )
                        return CheckResult(is_valid=True, branch=branch, issues=[])
                    except Exception as e:
                        logger.error(
                            "Auto-recovery failed",
                            branch=branch,
                            error=str(e),
                        )
                        # Preserve original consistency error in message
                        issues.append(
                            f"{consistency_error}. "
                            f"Auto-recovery failed: {e}. "
                            f"Manual fix: vibe3 flow rebuild {task_issue} --yes"
                        )

            is_valid = len(issues) == 0
            logger.bind(
                branch=branch, is_valid=is_valid, issues_count=len(issues)
            ).debug("Check completed")
            return CheckResult(
                is_valid=is_valid, issues=issues, warnings=warnings, branch=branch
            )

    def verify_all_flows(
        self,
        status: str | list[str] | None = "active",
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> list[CheckResult]:
        """Run consistency checks for flows in the store.

        Args:
            status: Filter flows by status(es). None checks all flows.
            on_progress: Optional callback invoked after each branch check.
                Receives (current_index, total_count, branch_name).
        """
        # Initialize PR cache (optimization: 1 API call instead of N)
        self._initialize_pr_cache()

        all_flows = self.store.get_all_flows()
        if status:
            statuses = [status] if isinstance(status, str) else status
            all_flows = [f for f in all_flows if f.get("flow_status") in statuses]

        # Filter out protected branches (main, master, develop, etc.)
        # These should never be treated as flow branches
        all_flows = [
            f
            for f in all_flows
            if f.get("branch") not in self.protected_branches
            and not str(f.get("branch", "")).startswith("origin/")
        ]

        results = []
        total = len(all_flows)
        for i, flow in enumerate(all_flows):
            results.append(self._check_branch(flow["branch"]))
            if on_progress:
                on_progress(i, total, flow["branch"])
        return results

    def auto_fix(self, issues: list[str], *, branch: str | None = None) -> FixResult:
        """Auto-fix local consistency issues for a branch."""
        branch = branch or self.git_client.get_current_branch()
        fixed: list[str] = []

        unfixed = issues
        if unfixed:
            hint = (
                "  Some issues cannot be auto-fixed. "
                "Try 'vibe3 check --init' or check manually."
            )
            error = (
                "Could not auto-fix:\n"
                + "\n".join(f"  - {i}" for i in unfixed)
                + f"\n{hint}"
            )
            return FixResult(success=False, error=error)
        return FixResult(success=True, applied=fixed)
