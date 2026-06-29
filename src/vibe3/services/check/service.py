"""Check service implementation for verifying handoff store consistency."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from loguru import logger

from vibe3.clients import (
    GitClient,
    GitHubClient,
    GitHubClientProtocol,
    SQLiteClient,
    load_sync_rules,
)
from vibe3.config import VibeConfig
from vibe3.models import CheckResult, IssueState
from vibe3.services.check.lock import check_lock
from vibe3.services.check.pr_service import CheckPRService
from vibe3.services.check.remote import (
    CheckRemote,
    issue_state_from_payload,
)
from vibe3.services.flow.status import FlowStatusService
from vibe3.services.pr.service import PRService

if TYPE_CHECKING:
    from vibe3.models import PRResponse


@dataclass
class FixResult:
    """Result of auto-fix operation."""

    success: bool
    error: str | None = None
    applied: list[str] = field(default_factory=list)


class CheckService(CheckRemote):
    """Service for verifying handoff store consistency and auto-fixing issues."""

    # Flow statuses that should be skipped for handoff/ref checks
    # Issue #3189: review/failed are PR-backed terminal states — treat as inactive.
    INACTIVE_FLOW_STATUSES = ("done", "aborted", "stale", "review", "failed")
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
        # Load sync rules for local domain checks
        self._sync_rules = load_sync_rules()

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
        from vibe3.services.shared.labels import (
            get_conflicting_states,
            get_highest_priority_state,
            normalize_labels,
        )

        labels = normalize_labels(issue_payload.get("labels", []))

        if not get_conflicting_states(labels):
            return ([], [], None)

        target_label = get_highest_priority_state(labels)
        if target_label is None:
            logger.bind(domain="check", action="fix").warning(
                f"Issue #{issue_number} has multiple state labels with "
                f"unknown states: {[lb for lb in labels if lb.startswith('state/')]}"
            )
            return (
                [],
                [
                    f"Issue #{issue_number} has multiple state labels "
                    f"({', '.join(lb for lb in labels if lb.startswith('state/'))}) "
                    f"with unknown state, manual fix required"
                ],
                None,
            )

        # Resolve to IssueState enum
        target_state = IssueState.from_label(target_label)
        assert (
            target_state is not None
        )  # get_highest_priority_state guarantees known state
        state_labels = [lb for lb in labels if lb.startswith("state/")]

        # Auto-fix using LabelService (atomic: add new, remove old)
        try:
            from vibe3.services.shared.label_service import LabelService

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
        with check_lock(branch, self.git_client) as acquired:
            if not acquired:
                return CheckResult(
                    is_valid=False,
                    issues=[
                        f"Check skipped for '{branch}' (lock held by another process)"
                    ],
                    branch=branch,
                )

            from vibe3.services.check.rule_checks import (
                RULES,
                CheckContext,
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

            # ---- gather data ----
            branch_missing = False
            try:
                output = self.git_client._run(["branch", "--list", branch])
                if not output.strip():
                    from vibe3.services.flow.service import FlowService

                    if not branch.startswith(FlowService.SAFE_BRANCH_PREFIX):
                        branch_missing = True
            except Exception as e:
                logger.bind(domain="check", branch=branch).warning(
                    f"Failed to verify local branch existence: {e}"
                )

            from vibe3.services.issue.flow import IssueFlowService

            issue_flow_service = IssueFlowService(store=self.store)
            task_issue = issue_flow_service.resolve_task_issue_number(branch)
            issue_links = self.store.get_issue_links(branch)
            task_issues = [lnk for lnk in issue_links if lnk["issue_role"] == "task"]

            task_issue_closed = False
            orchestration_state: IssueState | None = None
            issue_payload: dict | None = None
            issue_labels: list[str] = []
            issue_labels_loaded = False
            if task_issue:
                from vibe3.clients import GITHUB_DEFAULT_VIEW_FIELDS
                from vibe3.services.shared.labels import normalize_labels

                issue = self.github_client.view_issue(
                    task_issue, fields=list(GITHUB_DEFAULT_VIEW_FIELDS)  # type: ignore[call-overload]
                )
                if issue == "network_error":
                    issues.append(
                        f"Cannot verify task issue #{task_issue}: network/auth error"
                    )
                elif not issue:
                    issues.append(f"Task issue #{task_issue} not found on GitHub")
                elif isinstance(issue, dict):
                    issue_payload = issue
                    raw_labels = issue_payload.get("labels")
                    if isinstance(raw_labels, list):
                        issue_labels = normalize_labels(raw_labels)
                        issue_labels_loaded = True
                    orchestration_state = issue_state_from_payload(issue)
                    if str(issue.get("state", "")).upper() == "CLOSED":
                        task_issue_closed = True

                    # multi_state_label_fix (inline - modifies orchestration_state)
                    if self._sync_rules.local.multi_state_label_fix.enabled:
                        label_warnings, label_issues, fixed_state = (
                            self._check_multiple_state_labels(task_issue, issue_payload)
                        )
                        warnings.extend(label_warnings)
                        issues.extend(label_issues)
                        if fixed_state is not None:
                            orchestration_state = fixed_state
                            issue_labels = [fixed_state.to_label()]

            if len(task_issues) > 1:
                issues.append(f"Multiple task issues for branch '{branch}'")

            flow_status = flow_data.get("flow_status", "active")
            is_active_flow = flow_status not in self.INACTIVE_FLOW_STATUSES

            # ---- recovery service (shared by multiple rules) ----
            from vibe3.services.flow.recovery import FlowRecoveryService

            self.recovery_svc = FlowRecoveryService(
                store=self.store,
                git_client=self.git_client,
                github_client=self.github_client,
            )

            # ---- build context and execute rules ----
            ctx = CheckContext(
                branch=branch,
                flow_data=flow_data,
                flow_status=flow_status,
                is_active_flow=is_active_flow,
                task_issue=task_issue,
                task_issue_closed=task_issue_closed,
                orchestration_state=orchestration_state,
                issue_payload=issue_payload,
                issue_labels=issue_labels,
                issue_labels_loaded=issue_labels_loaded,
                branch_missing=branch_missing,
                issues=issues,
                warnings=warnings,
            )

            for rule in RULES:
                result = rule(ctx, self)
                if result is not None:
                    return result

            # ---- read-only dependency check ----
            if task_issue and flow_status not in self.INACTIVE_FLOW_STATUSES:
                from vibe3.services.orchestra.coordination import CoordinationResolver
                from vibe3.services.shared import DependencyResolutionService

                resolver = CoordinationResolver(store=self.store)
                truth = resolver.resolve_coordination(branch, task_issue)
                if truth.blocked_by_issues:
                    unresolved = []
                    unresolved_details = []
                    for dep in truth.blocked_by_issues:
                        resolution = DependencyResolutionService.is_dependency_resolved(
                            dep,
                            github_client=self.github_client,
                            repo=None,  # current CheckService doesn't carry repo
                        )
                        if not resolution.resolved:
                            unresolved.append(dep)
                            unresolved_details.append(
                                f"#{resolution.issue_number} "
                                f"(state={resolution.github_state or 'unknown'})"
                            )
                    if unresolved:
                        warnings.append(
                            f"Unresolved dependencies: {', '.join(unresolved_details)}"
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

    def clean_orchestra_scanned_with_assignee(self) -> int:
        """Remove orchestra-scanned label from issues with manager assignee.

        orchestra-scanned is a roadmap-intake mechanism to mark "not for intake".
        When an issue gets an assignee (e.g., via vibe-roadmap dependency resolution),
        it should have orchestra-scanned removed so assignee-pool can process it.

        Returns:
            Number of issues cleaned.
        """
        if not self._sync_rules.local.orchestra_scanned_assignee_cleanup.enabled:
            return 0

        import subprocess
        import time

        from vibe3.config import load_orchestra_config

        config = load_orchestra_config()
        cleaned_count = 0

        try:
            raw_issues = self.github_client.list_issues(
                limit=100,
                state="open",
                label="orchestra-scanned",
                repo=config.repo,
            )

            manager_usernames = set(config.manager_usernames)

            for issue in raw_issues:
                number = issue.get("number")
                if not isinstance(number, int):
                    continue

                assignees = issue.get("assignees", [])
                if not isinstance(assignees, list):
                    continue

                has_manager_assignee = any(
                    isinstance(a, dict) and a.get("login") in manager_usernames
                    for a in assignees
                )

                if has_manager_assignee:
                    try:
                        cmd = [
                            "gh",
                            "issue",
                            "edit",
                            str(number),
                            "--remove-label",
                            "orchestra-scanned",
                        ]
                        if config.repo:
                            cmd.extend(["--repo", config.repo])

                        subprocess.run(cmd, capture_output=True, text=True, check=True)
                        logger.bind(domain="check").info(
                            f"Removed orchestra-scanned from issue #{number} "
                            f"(has manager assignee)"
                        )
                        cleaned_count += 1
                        time.sleep(0.5)
                    except subprocess.CalledProcessError as exc:
                        logger.bind(domain="check").warning(
                            f"Failed to remove orchestra-scanned from issue #{number}: "
                            f"{exc.stderr}"
                        )

        except Exception as exc:
            logger.bind(domain="check").error(
                f"Failed to clean orchestra-scanned issues: {exc}"
            )

        return cleaned_count

    def enforce_label_constraints_remote(self) -> int:
        """Scan remote open issues for label constraint violations and auto-fix.

        This complements the per-flow constraint check
        (rule_label_constraint_enforcement) by scanning
        issues that have no local flow scene.

        Returns:
            Number of issues with violations fixed.
        """
        if not self._sync_rules.local.label_constraint_enforcement.enabled:
            return 0

        import subprocess
        import time

        from vibe3.config import load_orchestra_config
        from vibe3.services.check.label_constraints import check_constraints
        from vibe3.services.shared.labels import normalize_labels

        config = load_orchestra_config()
        fixed_count = 0

        label_filters = ("orchestra-scanned",) + tuple(
            state.to_label() for state in IssueState
        )
        seen_numbers: set[int] = set()

        for label_filter in label_filters:
            try:
                raw_issues = self.github_client.list_issues(
                    limit=100,
                    state="open",
                    label=label_filter,
                    repo=config.repo,
                )
            except Exception as exc:
                logger.bind(domain="check", label_filter=label_filter).error(
                    f"Failed to list issues for label constraint enforcement: {exc}"
                )
                continue

            for issue in raw_issues:
                number = issue.get("number")
                if not isinstance(number, int):
                    continue
                if number in seen_numbers:
                    continue
                seen_numbers.add(number)

                labels = normalize_labels(issue.get("labels", []))
                assignees = issue.get("assignees", [])
                assignee = (
                    assignees[0].get("login")
                    if isinstance(assignees, list) and assignees
                    else None
                )

                violations = check_constraints(labels=set(labels), assignee=assignee)
                if not violations:
                    continue

                labels_to_remove: set[str] = set()
                for v in violations:
                    if v.constraint_name == "single_state_label":
                        from vibe3.services.shared.labels import (
                            get_highest_priority_state,
                        )

                        state_labels = [lb for lb in labels if lb.startswith("state/")]
                        keep = get_highest_priority_state(state_labels)
                        if keep:
                            labels_to_remove.update(
                                lb for lb in state_labels if lb != keep
                            )
                    elif v.constraint_name in (
                        "no_state_without_assignee",
                        "ready_requires_assignee",
                    ):
                        labels_to_remove.update(
                            lb for lb in labels if lb.startswith("state/")
                        )
                    elif v.constraint_name == "scanned_forbids_state":
                        labels_to_remove.add("orchestra-scanned")
                    elif v.constraint_name == "scanned_governed_no_assignee":
                        labels_to_remove.update(
                            {"orchestra-scanned", "orchestra-governed"}
                        )

                if not labels_to_remove:
                    continue

                try:
                    for lb in sorted(labels_to_remove):
                        cmd = [
                            "gh",
                            "issue",
                            "edit",
                            str(number),
                            "--remove-label",
                            lb,
                        ]
                        if config.repo:
                            cmd.extend(["--repo", config.repo])
                        subprocess.run(cmd, capture_output=True, text=True, check=True)
                        time.sleep(0.3)

                    logger.bind(domain="check").info(
                        f"Fixed {len(violations)} label constraint violations "
                        f"on remote issue #{number}: "
                        f"removed {sorted(labels_to_remove)}"
                    )
                    fixed_count += 1
                except subprocess.CalledProcessError as exc:
                    logger.bind(domain="check").error(
                        f"Failed to fix label constraints on #{number}: "
                        f"{exc.stderr}"
                    )

        return fixed_count
