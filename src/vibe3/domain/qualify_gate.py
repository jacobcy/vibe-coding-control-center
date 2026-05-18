"""Domain service for qualify gate logic.

Extracted from StateLabelDispatchService to provide clean domain-layer API
for dependency and blocking checks during dispatch.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_labels import GhIssueLabelPort
from vibe3.models.coordination_truth import CoordinationTruth
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.services.convention_resolver import ConventionResolver
from vibe3.services.coordination_resolver import CoordinationResolver
from vibe3.services.flow_resume_resolver import infer_resume_label

if TYPE_CHECKING:
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.orchestra.flow_dispatch import FlowManager


class QualifyGateService:
    """Domain service for qualify gate logic.

    Handles dependency resolution and blocking state management
    during dispatch intent emission.
    """

    def __init__(
        self,
        config: OrchestraConfig,
        github: GitHubClient,
        store: "SQLiteClient",
        flow_manager: "FlowManager",
    ) -> None:
        """Initialize qualify gate service.

        Args:
            config: Orchestra configuration
            github: GitHub client for API calls
            store: SQLite client for flow state
            flow_manager: Flow manager for branch operations
        """
        self.config = config
        self._github = github
        self._store = store
        self._flow_manager = flow_manager
        resolver = ConventionResolver.from_repo()
        self._convention = resolver.resolve()
        self._coordination_resolver = CoordinationResolver(store=store)

    def run_qualify_gate(
        self,
        issue: IssueInfo,
        branch: str,
        flow_state: dict[str, object] | None,
        labels: list[str],
        trigger_state: IssueState,
    ) -> IssueState | None:
        """Run the Qualify Gate for an issue to resolve dependencies and blocking.

        Decision order:
        1. Resolve body/local truth
        2. Align blocked cache/label if needed
        3. If still blocked after alignment, skip
        4. If unblocked, continue dependency/worktree checks

        Args:
            issue: Issue to check
            branch: Git branch for this issue
            flow_state: Current flow state from store
            labels: Current issue labels
            trigger_state: The trigger state being evaluated

        Returns:
            Target IssueState if the issue passes the gate and can be dispatched,
            None if the issue is blocked and should be skipped.
        """
        # Step 1: Resolve body/local truth (remote-first)
        truth = self._coordination_resolver.resolve_coordination(branch, issue.number)

        # Step 2: Blocked truth alignment — body truth is authoritative
        if truth.is_blocked:
            self._align_blocked_state(
                issue_number=issue.number,
                branch=branch,
                truth=truth,
                labels=labels,
                flow_state=flow_state,
            )
            return None

        # Step 2b: Body truth NOT blocked, but local/label may be stale
        if self._has_stale_blocked_state(truth, labels, flow_state):
            target_label = self._auto_resume_blocked(
                issue_number=issue.number,
                branch=branch,
                labels=labels,
                flow_state=flow_state,
            )
            # Re-read flow_state after auto-resume for subsequent checks
            flow_state = self._store.get_flow_state(branch)
            # If no flow_state after resume, return the auto-resume target
            if not flow_state:
                return target_label

        # Step 3: Structural checks require flow_state
        if not flow_state:
            if trigger_state.to_label() in labels:
                return trigger_state
            return None

        # Step 4: Check worktree health (structural only — no semantic blocking)
        if not self._check_worktree_health(issue, branch, truth):
            return None

        # Step 5: Check dependency block (structural)
        if not self._check_dependencies(issue, branch, truth, labels):
            return None

        # Step 6: All clear
        if trigger_state.to_label() in labels:
            return trigger_state
        return None

    def qualify_blocked_issue(self, issue: IssueInfo) -> IssueState | None:
        """Run qualify gate for a blocked issue at dispatch intent time.

        Called by GlobalDispatchCoordinator instead of collection-time scanning.

        Args:
            issue: Issue to qualify

        Returns:
            Target IssueState to dispatch to, or None if still blocked.
        """
        flow = self._flow_manager.get_flow_for_issue(issue.number)
        branch = str(flow.get("branch") or "").strip() if flow else ""
        if not branch:
            return None

        flow_state = self._store.get_flow_state(branch)
        return self.run_qualify_gate(
            issue, branch, flow_state, list(issue.labels), IssueState.BLOCKED
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _align_blocked_state(
        self,
        issue_number: int,
        branch: str,
        truth: CoordinationTruth,
        labels: list[str],
        flow_state: dict[str, object] | None,
    ) -> None:
        """Align local cache and remote label to body blocked truth.

        Ensures local flow_state has flow_status='blocked' and blocked fields
        match the remote truth. Adds state/blocked label if missing.
        """
        blocked_label = self._convention.state_label(self._convention.blocked_label)

        # Align local cache
        if not flow_state or flow_state.get("flow_status") != "blocked":
            self._store.update_flow_state(
                branch,
                flow_status="blocked",
                blocked_reason=truth.blocked_reason,
                blocked_by_issue=truth.blocked_by_issue,
            )
            append_orchestra_event(
                "dispatcher",
                f"qualify_gate align_blocked #{issue_number}: "
                "local cache synced to blocked from body truth",
            )

        # Align remote label
        if blocked_label not in labels:
            try:
                label_port = GhIssueLabelPort(repo=self.config.repo)
                label_port.add_issue_label(issue_number, blocked_label)
            except Exception as exc:
                logger.bind(domain="orchestra").warning(
                    f"Failed to add {blocked_label} during alignment: {exc}"
                )

        append_orchestra_event(
            "dispatcher",
            f"qualify_gate skip #{issue_number}: "
            "blocked per body truth (projection state or payload)",
        )

    def _has_stale_blocked_state(
        self,
        truth: CoordinationTruth,
        labels: list[str],
        flow_state: dict[str, object] | None,
    ) -> bool:
        """Check if local/label indicate blocked but body truth does not.

        Stale state = local has blocked_by_issue or blocked_reason, or
        label has state/blocked, but truth.is_blocked is False.
        Requires flow_state to be present — without it there is nothing to resume.
        """
        if not flow_state:
            return False

        blocked_label = self._convention.state_label(self._convention.blocked_label)
        label_blocked = blocked_label in labels
        local_blocked = bool(truth.blocked_by_issue or truth.blocked_reason)

        return label_blocked or local_blocked

    def _auto_resume_blocked(
        self,
        issue_number: int,
        branch: str,
        labels: list[str],
        flow_state: dict[str, object] | None,
    ) -> IssueState:
        """Auto-resume a blocked issue when body truth is not blocked.

        Clears local blocked cache and removes state/blocked label.
        Routes through restore label inference (Task 3 will unify this
        to task-resume service path).

        Args:
            flow_state: Original flow state used to infer target label
                before clearing.

        Returns:
            Target IssueState after auto-resume.
        """
        from vibe3.models.flow import FlowState

        # Determine target label BEFORE clearing (use original flow_state)
        if flow_state:
            fs_obj = FlowState.model_validate(flow_state)
            target_label = infer_resume_label(fs_obj)
        else:
            target_label = IssueState.CLAIMED

        # Clear local blocked cache
        self._store.update_flow_state(
            branch,
            flow_status="active",
            blocked_reason=None,
            blocked_by_issue=None,
        )
        self._store.add_event(
            branch,
            "flow_unblocked",
            "orchestra:qualify",
            detail=f"Auto-resume: body truth not blocked for #{issue_number}",
        )

        # Remove blocked label
        blocked_label = self._convention.state_label(self._convention.blocked_label)
        if blocked_label in labels:
            try:
                label_port = GhIssueLabelPort(repo=self.config.repo)
                label_port.remove_issue_label(issue_number, blocked_label)
                if target_label.to_label() not in labels:
                    label_port.add_issue_label(issue_number, target_label.to_label())
            except Exception as exc:
                logger.bind(domain="orchestra").warning(
                    f"Failed to sync unblock labels for #{issue_number}: {exc}"
                )

        append_orchestra_event(
            "dispatcher",
            f"qualify_gate auto_resume #{issue_number}: "
            f"cleared stale blocked state, restored to {target_label.value}",
        )

        return target_label

    def _check_worktree_health(
        self,
        issue: IssueInfo,
        branch: str,
        truth: CoordinationTruth,
    ) -> bool:
        """Check worktree structural health.

        Returns True if worktree is healthy (dispatch can continue),
        False if blocked due to structural failure.
        """
        worktree_path = truth.worktree_path
        if not worktree_path or not isinstance(worktree_path, str):
            return True

        wt_path = Path(worktree_path)
        if not wt_path.exists():
            reason = f"Worktree path does not exist: {worktree_path}"
            from vibe3.services.flow_service import FlowService

            FlowService(store=self._store).block_flow(
                branch=branch,
                reason=reason,
                actor="orchestra:dispatcher",
            )
            append_orchestra_event(
                "dispatcher",
                f"qualify_gate skip #{issue.number}: {reason}",
            )
            return False

        # Validate branch matches using git
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(wt_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            actual_branch = result.stdout.strip()
            if actual_branch != branch:
                reason = (
                    f"Worktree branch mismatch: expected {branch}, "
                    f"got {actual_branch}"
                )
                from vibe3.services.flow_service import FlowService

                FlowService(store=self._store).block_flow(
                    branch=branch,
                    reason=reason,
                    actor="orchestra:dispatcher",
                )
                append_orchestra_event(
                    "dispatcher",
                    f"qualify_gate skip #{issue.number}: {reason}",
                )
                return False
        except Exception:
            pass  # Can't read HEAD, skip validation

        return True

    def _check_dependencies(
        self,
        issue: IssueInfo,
        branch: str,
        truth: CoordinationTruth,
        labels: list[str],
    ) -> bool:
        """Check dependency resolution.

        Returns True if dependencies are satisfied (dispatch can continue),
        False if blocked due to unresolved dependencies.
        """
        dependencies = truth.dependencies
        if not dependencies:
            return True

        unresolved = [d for d in dependencies if not self._is_dependency_satisfied(d)]

        if not unresolved:
            return True

        blocked_label = self._convention.state_label(self._convention.blocked_label)
        blocked_by_issue = truth.blocked_by_issue

        if not blocked_by_issue:
            from vibe3.services.flow_service import FlowService

            FlowService(store=self._store).block_flow(
                branch=branch,
                reason="Blocked by unresolved dependencies",
                blocked_by_issue=unresolved[0],
                actor="orchestra:dispatcher",
            )
        else:
            self._store.update_flow_state(
                branch,
                flow_status="blocked",
            )

        if blocked_label not in labels:
            try:
                label_port = GhIssueLabelPort(repo=self.config.repo)
                label_port.add_issue_label(issue.number, blocked_label)
            except Exception as exc:
                logger.bind(domain="orchestra").warning(
                    f"Failed to add {blocked_label}: {exc}"
                )

        return False

    def _get_issue_dependencies(self, issue_number: int) -> list[int]:
        """Get dependency issue numbers from flow_issue_links.

        Args:
            issue_number: The issue number to check for dependencies

        Returns:
            List of dependency issue numbers (empty if no dependencies)
        """
        flows = self._store.get_flows_by_issue(issue_number, role="task")
        if not flows:
            return []

        branch = str(flows[0].get("branch") or "").strip()
        if not branch:
            return []

        return self._store.get_dependency_links(branch)

    def _is_dependency_satisfied(self, dep_issue_number: int) -> bool:
        """Check if dependency issue has completed.

        A dependency is satisfied when:
        - Issue is closed (Done or Aborted)

        Args:
            dep_issue_number: The dependency issue number to check

        Returns:
            True if dependency is satisfied, False otherwise
        """
        payload = self._github.view_issue(dep_issue_number, repo=self.config.repo)
        if not isinstance(payload, dict):
            return False

        state = payload.get("state")
        if state == "closed":
            return True

        return False
