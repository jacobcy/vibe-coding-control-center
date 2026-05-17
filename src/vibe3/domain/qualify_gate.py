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
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.orchestra.logging import append_orchestra_event
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

    def run_qualify_gate(
        self,
        issue: IssueInfo,
        branch: str,
        flow_state: dict[str, object] | None,
        labels: list[str],
        trigger_state: IssueState,
    ) -> IssueState | None:
        """Run the Qualify Gate for an issue to resolve dependencies and blocking.

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
        if not flow_state:
            if IssueState.BLOCKED.to_label() in labels:
                append_orchestra_event(
                    "dispatcher",
                    f"qualify_gate skip #{issue.number}: "
                    "local flow state missing but remote is blocked",
                )
                return None
            if trigger_state.to_label() in labels:
                return trigger_state
            return None

        # Step 1: Check manual block
        blocked_reason = flow_state.get("blocked_reason")
        if blocked_reason and str(blocked_reason).strip():
            if IssueState.BLOCKED.to_label() not in labels:
                try:
                    label_port = GhIssueLabelPort(repo=self.config.repo)
                    label_port.add_issue_label(issue.number, "state/blocked")
                except Exception as exc:
                    logger.bind(domain="orchestra").warning(
                        f"Failed to add state/blocked: {exc}"
                    )
            return None

        # Step 1.5: Check worktree health (local state validation)
        worktree_path = flow_state.get("worktree_path")
        if worktree_path and isinstance(worktree_path, str):
            wt_path = Path(worktree_path)
            if not wt_path.exists():
                reason = f"Worktree path does not exist: {worktree_path}"
                self._store.update_flow_state(
                    branch,
                    blocked_reason=reason,
                )
                self._store.add_event(
                    branch,
                    "flow_blocked",
                    "orchestra:dispatcher",
                    detail=reason,
                )
                if IssueState.BLOCKED.to_label() not in labels:
                    try:
                        label_port = GhIssueLabelPort(repo=self.config.repo)
                        label_port.add_issue_label(issue.number, "state/blocked")
                    except Exception as exc:
                        logger.bind(domain="orchestra").warning(
                            f"Failed to add state/blocked for #{issue.number}: {exc}"
                        )
                append_orchestra_event(
                    "dispatcher",
                    f"qualify_gate skip #{issue.number}: {reason}",
                )
                return None
            # Validate branch matches using git (works with linked worktrees)
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
                    self._store.update_flow_state(
                        branch,
                        blocked_reason=reason,
                    )
                    self._store.add_event(
                        branch,
                        "flow_blocked",
                        "orchestra:dispatcher",
                        detail=reason,
                    )
                    if IssueState.BLOCKED.to_label() not in labels:
                        try:
                            label_port = GhIssueLabelPort(repo=self.config.repo)
                            label_port.add_issue_label(issue.number, "state/blocked")
                        except Exception as exc:
                            logger.bind(domain="orchestra").warning(
                                f"Failed to add state/blocked for "
                                f"#{issue.number}: {exc}"
                            )
                    append_orchestra_event(
                        "dispatcher",
                        f"qualify_gate skip #{issue.number}: {reason}",
                    )
                    return None
            except Exception:
                pass  # Can't read HEAD, skip validation (don't block on read error)

        # Step 2: Check dependency block
        dependencies = self._get_issue_dependencies(issue.number)
        unresolved = []
        if dependencies:
            unresolved = [
                d for d in dependencies if not self._is_dependency_satisfied(d)
            ]

        if unresolved:
            if not flow_state.get("blocked_by_issue"):
                self._store.update_flow_state(
                    branch,
                    blocked_by_issue=unresolved[0],
                    blocked_reason="Blocked by unresolved dependencies",
                )
                if IssueState.BLOCKED.to_label() not in labels:
                    try:
                        label_port = GhIssueLabelPort(repo=self.config.repo)
                        label_port.add_issue_label(issue.number, "state/blocked")
                    except Exception as exc:
                        logger.bind(domain="orchestra").warning(
                            f"Failed to add state/blocked for #{issue.number}: {exc}"
                        )
                self._store.add_event(
                    branch,
                    "flow_blocked",
                    "orchestra:dispatcher",
                    detail="Blocked by unresolved dependencies",
                )
            return None

        # Step 3: All clear — determine target and perform unblock side effects

        # Issue is not in blocked state: confirm trigger label (no unblock needed)
        if IssueState.BLOCKED.to_label() not in labels and not flow_state.get(
            "blocked_by_issue"
        ):
            if trigger_state.to_label() in labels:
                return trigger_state
            return None

        from vibe3.models.flow import FlowState

        fs_obj = FlowState.model_validate(flow_state)
        target_label = infer_resume_label(fs_obj)

        if flow_state.get("blocked_by_issue"):
            dep_issue = flow_state.get("blocked_by_issue")
            source_pr = None
            if isinstance(dep_issue, int):
                dep_flows = self._store.get_flows_by_issue(dep_issue, role="task")
                for df in dep_flows:
                    if df.get("pr_number"):
                        source_pr = df.get("pr_number")
                        break

            refs: dict[str, str] = {}
            if source_pr:
                refs["source_pr"] = str(source_pr)

            # Unblock: restore flow from blocked metadata
            # IssueState (GitHub label) and FlowStatus (internal state)
            # are separate:
            # - FlowStatus: internal state machine (active/done/stale/aborted)
            # - IssueState: external GitHub label
            #   (ready/claimed/in-progress/handoff/review)
            # When unblocking, we clear blocked metadata
            self._store.update_flow_state(
                branch,
                blocked_by_issue=None,
                blocked_reason=None,
            )
            self._store.add_event(
                branch,
                "flow_unblocked",
                "orchestra:dispatcher",
                detail=f"Dependencies satisfied, target: {target_label.value}",
                refs=refs if refs else None,
            )

        if IssueState.BLOCKED.to_label() in labels:
            try:
                label_port = GhIssueLabelPort(repo=self.config.repo)
                label_port.remove_issue_label(issue.number, "state/blocked")
                if target_label.to_label() not in labels:
                    label_port.add_issue_label(issue.number, target_label.to_label())
            except Exception as exc:
                logger.bind(domain="orchestra").warning(
                    f"Failed to sync unblocked labels for #{issue.number}: {exc}"
                )

        return target_label

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

    def _get_issue_dependencies(self, issue_number: int) -> list[int]:
        """Get dependency issue numbers from flow_issue_links.

        Args:
            issue_number: The issue number to check for dependencies

        Returns:
            List of dependency issue numbers (empty if no dependencies)
        """
        # Query flows where this issue is task role
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

        # Check issue state
        state = payload.get("state")
        if state == "closed":
            return True  # Issue closed → dependency satisfied

        return False
