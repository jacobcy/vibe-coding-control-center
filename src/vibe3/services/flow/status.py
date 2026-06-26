"""Flow status management service for marking and updating flow states."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import GitClient, GitHubClient, SQLiteClient
from vibe3.models import IssueState

if TYPE_CHECKING:
    from vibe3.models import PRResponse


class FlowStatusService:
    """Service for managing flow status transitions and related side effects."""

    def __init__(
        self,
        store: SQLiteClient,
        git_client: GitClient,
        github_client: GitHubClient,
    ) -> None:
        """Initialize FlowStatusService with required dependencies.

        Args:
            store: SQLiteClient for flow_state and event storage
            git_client: GitClient for branch operations
            github_client: GitHubClient for issue operations
        """
        self.store = store
        self.git_client = git_client
        self.github_client = github_client

    def rebuild_stale_ready_flow(
        self,
        branch: str,
        *,
        task_issue: int | None,
        issue_payload: dict | None,
    ) -> bool:
        """Rebuild stale canonical ready flow using FlowRebuildUsecase."""
        from vibe3.services.flow.rebuild import FlowRebuildUsecase
        from vibe3.services.issue.flow import IssueFlowService

        issue_number = task_issue
        if issue_number is None:
            issue_flow_service = IssueFlowService(store=self.store)
            issue_number = issue_flow_service.resolve_task_issue_number(branch)
            if issue_number is None:
                return False

        from vibe3.models import IssueInfo

        issue = IssueInfo(
            number=issue_number,
            title=str((issue_payload or {}).get("title") or f"Issue {issue_number}"),
            state=IssueState.READY,
            labels=[IssueState.READY.to_label()],
        )

        FlowRebuildUsecase(
            store=self.store,
            git_client=self.git_client,
            github_client=self.github_client,
        ).rebuild_issue_flow(
            issue=issue,
            branch=branch,
            reason="stale ready flow rebuild",
            include_remote=False,
            ensure_worktree=True,
        )
        return True

    def mark_flow_status(
        self,
        branch: str,
        status: str,
        reason: str,
        event_type: str,
        action: str,
        record_event: bool = True,
    ) -> None:
        """Generic method to mark flow status and record event."""
        logger.bind(
            domain="check",
            action=action,
            branch=branch,
        ).info(f"{action}: {reason}")
        self.store.update_flow_state(branch, flow_status=status)
        if record_event:
            self.store.add_event(
                branch,
                event_type,
                "system",
                f"Flow auto-{status}: {reason}",
            )

    @staticmethod
    def is_task_branch(branch: str) -> bool:
        """Check if branch follows the task/issue-N auto-flow pattern."""
        return branch.startswith("task/issue-")

    def mark_flow_done(
        self,
        branch: str,
        reason: str,
    ) -> dict[str, int | None]:
        """Mark a flow as done and record the event.

        For flows with role=task issue links, auto-closes the linked GitHub issue
        when no other active flows exist for the same issue.

        Multi-flow binding protection: If the same task issue is linked to multiple
        active flows (e.g., task/issue-123 and dev/issue-123), the issue is NOT
        closed until all active flows are done.

        Note: Branch cleanup is deferred to 'vibe3 check --clean-branch'.
        This keeps check fast and allows code reuse.

        Returns:
            Dict with suggestions, e.g., {"issue_to_close": 123}
            where issue_to_close is set only when auto-close was needed.
        """
        try:
            from vibe3.analysis import snapshot_service

            snapshot_service.save_branch_baseline(branch)
        except Exception as e:
            logger.warning(f"Failed to save branch baseline on auto-complete: {e}")

        self.mark_flow_status(
            branch,
            "done",
            reason,
            "flow_auto_completed",
            "auto_complete_flow",
            record_event=False,
        )

        # Fetch task issue once for both event publish and close logic
        task_issue = self.store.get_task_issue_number(branch)

        # Publish FlowCompleted event if we have a valid issue context
        if task_issue:
            from vibe3.models import FlowCompleted, publish

            publish(
                FlowCompleted(
                    issue_number=task_issue,
                    branch=branch,
                    completed_state="done",
                )
            )

        suggestions: dict[str, int | None] = {"issue_to_close": None}
        # Only close issue if there's an explicit task-role binding.
        # Do NOT fallback to branch name parsing - that would incorrectly close
        # issues that are only linked as related/dependency.
        if not task_issue:
            return suggestions

        # Multi-flow binding protection: Check if other active flows exist
        # for the same task issue before closing.
        all_task_flows = self.store.get_flows_by_issue(task_issue, role="task")
        other_active_flows = [
            f
            for f in all_task_flows
            if f["branch"] != branch and f.get("flow_status") == "active"
        ]

        if other_active_flows:
            logger.bind(
                domain="check",
                action="auto_complete_flow",
                branch=branch,
                issue_number=task_issue,
                other_active_count=len(other_active_flows),
            ).warning(
                f"Skipping auto-close for issue #{task_issue}: "
                f"other active flows exist ({len(other_active_flows)}"
            )
            return suggestions

        # Safe to close: this is the only active flow for this task issue
        close_result = self.github_client.close_issue_if_open(
            issue_number=task_issue,
            closing_comment=(
                f"PR merged. Flow '{branch}' completed. "
                "Closed automatically by vibe check."
            ),
        )

        # Track if issue was actually closed (vs already_closed)
        if close_result == "closed":
            suggestions["issue_to_close"] = task_issue

        return suggestions

    def mark_flow_aborted(self, branch: str, reason: str) -> None:
        """Mark a flow as aborted and record the event."""
        self.mark_flow_status(
            branch, "aborted", reason, "flow_auto_aborted", "auto_abort_flow"
        )

    def mark_flow_stale(self, branch: str, reason: str) -> None:
        """Mark an empty active flow as stale and record the event."""
        self.mark_flow_status(
            branch, "stale", reason, "flow_auto_staled", "auto_stale_flow"
        )

    def transition_aborted_to_done(
        self,
        branch: str,
        reason: str,
        pr_number: int | None = None,
    ) -> None:
        """Transition an aborted flow to done with phase-level cleanup.

        Unlike mark_flow_done, this method:
        - Does NOT auto-close the issue (already closed)
        - Does NOT save branch snapshot (branch may be cleaned up)
        - DOES clean up stale planner_status, executor_status, reviewer_status
        - Records a flow_auto_transitioned event
        """
        self.store.update_flow_state(
            branch,
            flow_status="done",
            planner_status="done",
            executor_status="done",
            reviewer_status="done",
        )
        detail = f"Aborted flow transitioned to done: {reason}"
        if pr_number:
            detail += f" (PR #{pr_number})"
        self.store.add_event(
            branch,
            "flow_auto_transitioned",
            "system",
            detail,
        )
        logger.bind(
            domain="flow",
            action="transition_aborted_to_done",
            branch=branch,
            pr_number=pr_number,
        ).success(f"Transitioned aborted flow to done: {reason}")

    def evaluate_aborted_to_done_eligibility(
        self,
        flow_state: dict[str, object] | None,
        branch: str,
        cached_pr: PRResponse | None = None,
    ) -> tuple[bool, int | None]:
        """Centralized heuristic: is an aborted flow eligible for done transition?

        Shared by qualify_gate and check reconcile rule to avoid logic drift.
        Returns ``(eligible, pr_number)``.

        Eligibility requires BOTH:
        - All lifecycle phases done (planner/executor/reviewer)
        - Delivery confirmed: ``pr_ref`` cached in flow record, ``cached_pr``
          merged, or a merged PR found via GitHub lookup

        Pass ``cached_pr`` to skip the GitHub API call when the caller already
        has PR data (e.g., CheckContext.branch_pr).
        """
        if not flow_state:
            return (False, None)

        phase_statuses = (
            flow_state.get("planner_status"),
            flow_state.get("executor_status"),
            flow_state.get("reviewer_status"),
        )
        if not all(s == "done" for s in phase_statuses):
            return (False, None)

        # Fast path: pr_ref cached in flow record
        if flow_state.get("pr_ref"):
            return (True, _coerce_pr_number(flow_state.get("pr_number")))

        # Cached PR from caller (e.g., CheckContext.branch_pr)
        if cached_pr is not None and cached_pr.merged_at is not None:
            return (True, cached_pr.number)

        # Slow path: query GitHub for merged PR
        try:
            prs = self.github_client.list_prs_for_branch(branch)
            for pr in prs:
                if pr.merged_at is not None:
                    return (True, pr.number)
        except Exception as e:
            logger.warning(
                f"PR lookup failed for aborted→done eligibility on {branch}: {e}"
            )
        return (False, None)


def _coerce_pr_number(value: object) -> int | None:
    """Coerce a flow_state pr_number value to int | None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None
