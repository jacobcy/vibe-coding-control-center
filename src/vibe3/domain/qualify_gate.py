"""Domain service for qualify gate logic.

Extracted from StateLabelDispatchService to provide clean domain-layer API
for dependency and blocking checks during dispatch.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients import GitClient, GitHubClient
from vibe3.models import (
    CoordinationTruth,
    FlowStatusResponse,
    IssueInfo,
    IssueState,
    OrchestraConfig,
)
from vibe3.services import (
    ConventionResolver,
    CoordinationResolver,
    FlowService,
    IssueFlowService,
    LabelService,
    TaskResumeOperations,
    infer_resume_label,
)

if TYPE_CHECKING:
    from vibe3.clients import SQLiteClient
    from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol


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
        flow_manager: "FlowManagerProtocol",
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

    def _terminalize_closed_issue(self, issue: IssueInfo, branch: str) -> None:
        """Terminalize local flow for a GitHub-closed issue."""
        if not branch:
            logger.debug(
                "qualify_gate: no branch for closed issue "
                f"#{issue.number}, skipping terminalization"
            )
            return

        from vibe3.observability import append_orchestra_event

        append_orchestra_event(
            "dispatcher",
            f"qualify_gate skip (#{issue.number}): "
            "issue closed on GitHub — terminalizing local flow",
        )
        from vibe3.services import FlowCleanupService

        FlowCleanupService(store=self._store).cleanup_flow_scene(
            branch,
            include_remote=False,
            terminate_sessions=True,
            keep_flow_record=True,
        )

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
        0. GitHub closed check (ALL states)
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
        # Step 0: GitHub closed check (ALL states)
        if issue.github_state and issue.github_state.upper() == "CLOSED":
            self._terminalize_closed_issue(issue, branch)
            return None

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

        Returns None when the issue remains blocked or should be skipped entirely
        (already closed on GitHub — terminalized and skipped).

        Args:
            issue: Issue to qualify

        Returns:
            Target IssueState to dispatch to, or None if still blocked.
        """

        if issue.github_state and issue.github_state.upper() == "CLOSED":
            flow = self._flow_manager.get_flow_for_issue(issue.number)
            branch = str(flow.get("branch") or "").strip() if flow else ""
            self._terminalize_closed_issue(issue, branch)
            return None

        flow = self._flow_manager.get_flow_for_issue(issue.number)
        branch = str(flow.get("branch") or "").strip() if flow else ""
        if not branch:
            return None

        flow_state = self._store.get_flow_state(branch)
        result = self.run_qualify_gate(
            issue, branch, flow_state, list(issue.labels), IssueState.BLOCKED
        )

        if result == IssueState.BLOCKED:
            return None

        return result

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
        from vibe3.observability import append_orchestra_event
        from vibe3.services import BlockedStateService

        blocked_label = self._convention.state_label(self._convention.blocked_label)
        label_blocked = blocked_label in labels

        if not flow_state or flow_state.get("flow_status") != "blocked":
            service = BlockedStateService(
                github_client=self._github,
                store=self._store,
            )
            service.write_cache(
                branch=branch,
                reason=truth.blocked_reason,
                blocked_by_issue=truth.blocked_by_issue,
                actor="system:qualify_gate",
            )
            append_orchestra_event(
                "dispatcher",
                f"qualify_gate align_blocked #{issue_number}: "
                "local cache synced to blocked from body truth",
            )

        if blocked_label not in labels:
            try:
                from vibe3.services import LabelService

                label_service = LabelService(repo=self.config.repo)
                label_service.confirm_issue_state(
                    issue_number,
                    IssueState.BLOCKED,
                    actor="orchestra:qualify_gate",
                    force=True,
                )
                label_blocked = True
            except Exception as exc:
                logger.bind(domain="orchestra").warning(
                    f"Failed to add {blocked_label} during alignment: {exc}"
                )

        event = self._format_blocked_skip_event(
            issue_number=issue_number,
            truth=truth,
            flow_state=flow_state,
            label_blocked=label_blocked,
        )
        append_orchestra_event("dispatcher", event)

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
        local_blocked = bool(
            flow_state.get("blocked_by_issue")
            or flow_state.get("blocked_reason")
            or flow_state.get("flow_status") == "blocked"
        )

        return label_blocked or local_blocked

    @staticmethod
    def _source_value(source: object | None) -> str:
        return str(value) if (value := getattr(source, "value", None)) else "none"

    @classmethod
    def _format_blocked_skip_event(
        cls,
        *,
        issue_number: int,
        truth: CoordinationTruth,
        flow_state: dict[str, object] | None,
        label_blocked: bool,
    ) -> str:
        blocked_by = f"#{truth.blocked_by_issue}" if truth.blocked_by_issue else "none"
        local_flow_status = (
            str(flow_state.get("flow_status") or "none") if flow_state else "none"
        )
        return (
            f"qualify_gate skip #{issue_number}: blocked per body truth "
            f"(projection_state={truth.projection_state or 'none'}, "
            f"projection_source={cls._source_value(truth.projection_state_source)}, "
            f"blocked_reason={truth.blocked_reason or 'none'}, "
            f"blocked_reason_source={cls._source_value(truth.blocked_reason_source)}, "
            f"blocked_by_issue={blocked_by}, "
            "blocked_by_issue_source="
            f"{cls._source_value(truth.blocked_by_issue_source)}, "
            f"local_flow_status={local_flow_status}, "
            f"label_blocked={label_blocked})"
        )

    def _auto_resume_blocked(
        self,
        issue_number: int,
        branch: str,
        labels: list[str],
        flow_state: dict[str, object] | None,
    ) -> IssueState:
        """Auto-resume a blocked issue when body truth is not blocked.

        Clears local blocked cache and removes state/blocked label.
        """
        from vibe3.models import FlowState
        from vibe3.observability import append_orchestra_event

        if flow_state:
            fs_obj = FlowState.model_validate(flow_state)
            target_label = infer_resume_label(fs_obj)
        else:
            target_label = IssueState.READY

        from typing import Literal, cast

        flow_status_value = (
            flow_state.get("flow_status", "blocked") if flow_state else "blocked"
        )
        flow = FlowStatusResponse(
            branch=branch,
            flow_slug=(
                str(flow_state.get("flow_slug") or branch) if flow_state else branch
            ),
            flow_status=cast(
                Literal["active", "blocked", "done", "stale", "aborted"],
                flow_status_value,
            ),
            latest_actor="orchestra:qualify",
            task_issue_number=issue_number,
        )
        operations = TaskResumeOperations(
            git_client=GitClient(),
            github_client=self._github,
            flow_service=FlowService(store=self._store),
            label_service=LabelService(repo=self.config.repo),
            issue_flow_service=IssueFlowService(store=self._store),
        )
        operations.reset_issue_to_ready(
            issue_number=issue_number,
            resume_kind="blocked",
            flow=flow,
            repo=self.config.repo,
            reason="qualify gate auto-resume",
            label_state="",
        )

        append_orchestra_event(
            "dispatcher",
            f"qualify_gate auto_resume #{issue_number}: "
            f"unblocked to {target_label.value}",
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
        from vibe3.observability import append_orchestra_event

        worktree_path = truth.worktree_path
        if not worktree_path or not isinstance(worktree_path, str):
            return True

        wt_path = Path(worktree_path)
        if not wt_path.exists():
            reason = f"Worktree path does not exist: {worktree_path}"
            from vibe3.services import BlockedStateService, LabelService

            service = BlockedStateService(
                store=self._store,
                github_client=self._github,
                label_service=LabelService(repo=self.config.repo),
            )
            service.block(
                branch=branch,
                reason=reason,
                actor="orchestra:dispatcher",
                issue_number=issue.number,
                event_type="flow_blocked",
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
                from vibe3.services import BlockedStateService, LabelService

                service = BlockedStateService(
                    store=self._store,
                    github_client=self._github,
                    label_service=LabelService(repo=self.config.repo),
                )
                service.block(
                    branch=branch,
                    reason=reason,
                    actor="orchestra:dispatcher",
                    issue_number=issue.number,
                    event_type="flow_blocked",
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

        # Use BlockedStateService for consistent three-source blocking
        from vibe3.services import BlockedStateService, LabelService

        service = BlockedStateService(
            store=self._store,
            github_client=self._github,
            label_service=LabelService(repo=self.config.repo),
        )
        service.block(
            branch=branch,
            reason="Blocked by unresolved dependencies",
            blocked_by_issue=truth.blocked_by_issue or unresolved[0],
            actor="orchestra:dispatcher",
            issue_number=issue.number,
            event_type="flow_blocked",
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
