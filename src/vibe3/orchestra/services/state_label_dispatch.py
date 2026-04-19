"""State-driven trigger service for manager/plan/run/review intent emission."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_labels import GhIssueLabelPort
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.execution.flow_dispatch import FlowManager
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import (
    IssueInfo,
    IssueState,
)
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.orchestra.queue_ordering import sort_ready_issues
from vibe3.roles.definitions import TriggerableRoleDefinition
from vibe3.runtime.service_protocol import GitHubEvent, ServiceBase

if TYPE_CHECKING:
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.execution.capacity_service import CapacityService


def _normalize_labels(raw_labels: object) -> list[str]:
    labels: list[str] = []
    if not isinstance(raw_labels, list):
        return labels
    for item in raw_labels:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name:
                labels.append(name)
    return labels


def _is_auto_task_branch(branch: str) -> bool:
    return branch.startswith("task/issue-")


class StateLabelDispatchService(ServiceBase):
    """Dispatch manager or downstream agents from issue state labels.

    The per-role dispatch logic (status_field, dispatch_predicate) is owned by
    TriggerableRoleDefinition. This service is a thin runtime loop that polls
    GitHub, filters using role-declared predicates, and publishes domain events.
    """

    event_types: list[str] = []

    @property
    def service_name(self) -> str:
        return (
            f"{type(self).__name__}("
            f"{self.role_def.trigger_name}:{self.role_def.trigger_state.value})"
        )

    def __init__(
        self,
        config: OrchestraConfig,
        *,
        github: GitHubClient | None = None,
        executor: ThreadPoolExecutor | None = None,
        flow_manager: FlowManager | None = None,
        registry: "SessionRegistryService | None" = None,
        capacity: "CapacityService | None" = None,
        role_def: TriggerableRoleDefinition,
    ) -> None:
        self.config = config
        self._executor = executor or ThreadPoolExecutor(
            max_workers=config.max_concurrent_flows,
        )
        self._github = github or GitHubClient()
        self._flow_manager = flow_manager or FlowManager(config, registry=registry)
        self._store = SQLiteClient()
        self._registry = registry
        self._capacity = capacity
        self._dispatch_guard = asyncio.Lock()
        self.role_def = role_def

    # trigger_name / trigger_state kept as properties for callers that access them.
    @property
    def trigger_name(self) -> str:
        return self.role_def.trigger_name

    @property
    def trigger_state(self) -> IssueState:
        return self.role_def.trigger_state

    async def handle_event(self, event: GitHubEvent) -> None:
        return

    async def collect_ready_issues(self) -> list[IssueInfo]:
        """Scan and return ready issues without dispatching.

        This method is for GlobalDispatchCoordinator to collect issues for
        capacity-aware dispatch. Capacity checking is done by coordinator.

        **Dependency Handling**:
        Issues with unresolved dependencies are marked as 'waiting' and excluded
        from the ready list. Only issues without dependencies or with all
        dependencies satisfied are returned as ready.

        Returns:
            Filtered and sorted ready issues list (excluding waiting issues)
        """
        async with self._dispatch_guard:
            raw_issues = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self._github.list_issues(
                    limit=100,
                    state="open",
                    assignee=None,
                    repo=self.config.repo,
                    label=self.role_def.trigger_state.to_label(),
                ),
            )

            ready = self._select_ready_issues(raw_issues)

            append_orchestra_event(
                "dispatcher",
                f"{self.service_name} collect: {len(ready)} ready issues",
            )
            return ready

    async def on_tick(self) -> None:
        """Periodic scan and async dispatch for the configured trigger state.

        **DEPRECATED**: This method bypasses capacity checks and should not be
        called directly. Use GlobalDispatchCoordinator.coordinate() instead,
        which properly checks capacity before emitting dispatch intents.

        This method is kept for backward compatibility but will raise a warning
        if called outside of GlobalDispatchCoordinator context.
        """
        import warnings

        warnings.warn(
            f"{self.service_name}.on_tick() is deprecated: "
            "bypasses capacity checks. Use GlobalDispatchCoordinator instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        ready = await self.collect_ready_issues()

        for issue in ready:
            try:
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} emitting dispatch-intent event "
                    f"for #{issue.number}",
                    level="DEBUG",
                )
                self._emit_dispatch_intent(issue)

                logger.bind(
                    domain="orchestra",
                    trigger=self.role_def.trigger_name,
                    issue=issue.number,
                ).debug("Dispatch-intent event emitted, handler will dispatch")
            except Exception as exc:
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} failed to emit event "
                    f"for #{issue.number}: {exc}",
                )
                logger.bind(
                    domain="orchestra",
                    trigger=self.role_def.trigger_name,
                    issue=issue.number,
                ).warning(f"State dispatch failed: {exc}")

    def _emit_dispatch_intent(self, issue: IssueInfo) -> None:
        from vibe3.domain import publish
        from vibe3.roles.registry import build_label_dispatch_event

        branch, _ = self._flow_context(issue.number)
        publish(
            build_label_dispatch_event(
                self.role_def,
                issue,
                branch=branch,
            )
        )

    def _flow_context(self, issue_number: int) -> tuple[str, dict[str, object] | None]:
        flow = self._flow_manager.get_flow_for_issue(issue_number)
        branch = str(flow.get("branch") or "").strip() if flow else ""
        if not branch:
            return "", None
        return branch, self._store.get_flow_state(branch)

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

        # Query dependency links for this branch
        import sqlite3

        with sqlite3.connect(self._store.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT issue_number FROM flow_issue_links "
                "WHERE branch = ? AND issue_role = 'dependency'",
                (branch,),
            )
            return [row[0] for row in cursor.fetchall()]

    def _is_dependency_satisfied(self, dep_issue_number: int) -> bool:
        """Check if dependency issue has completed (PR created).

        A dependency is satisfied when:
        - Issue is closed
        - Issue has state/done or state/merged label
        - Issue body/comments mention PR reference

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

        # Check for PR reference (completion marker)
        labels = _normalize_labels(payload.get("labels"))
        if "state/done" in labels or "state/merged" in labels:
            return True  # Task completed with PR

        # Check for PR in issue body or comments
        body = payload.get("body", "")
        if isinstance(body, str):
            if "pull request" in body.lower() or "pr #" in body.lower():
                return True  # PR mentioned → likely completed

        return False  # Dependency not yet satisfied

    def _mark_issue_waiting(
        self, issue_number: int, unresolved_deps: list[int]
    ) -> None:
        """Mark issue as waiting for dependencies.

        Updates flow_status to waiting, sets blocked_by_issue, records event,
        and syncs GitHub label.

        Args:
            issue_number: The issue number to mark as waiting
            unresolved_deps: List of unresolved dependency issue numbers
        """
        flows = self._store.get_flows_by_issue(issue_number, role="task")
        if not flows:
            return

        branch = str(flows[0].get("branch") or "").strip()
        if not branch:
            return

        # Update flow_status to waiting
        self._store.update_flow_state(
            branch,
            flow_status="waiting",
            blocked_by_issue=unresolved_deps[0],  # Primary dependency
            blocked_reason=f"Waiting for dependencies: #{unresolved_deps}",
        )

        # Add event
        self._store.add_event(
            branch,
            "dependency_waiting",
            "orchestra:dispatcher",
            detail=f"Waiting for dependencies: {unresolved_deps}",
            refs={"dependencies": [str(d) for d in unresolved_deps]},
        )

        # Sync GitHub label (use state/blocked for waiting)
        try:
            label_port = GhIssueLabelPort(repo=self.config.repo)
            label_port.add_issue_label(issue_number, "state/blocked")
        except Exception as exc:
            logger.bind(
                domain="orchestra",
                dispatcher=self.service_name,
                issue=issue_number,
            ).warning(f"Failed to add state/blocked label: {exc}")

    def _select_ready_issues(
        self, raw_issues: list[dict[str, object]]
    ) -> list[IssueInfo]:
        """Select ready issues, checking for unresolved dependencies.

        Issues with dependencies are marked as 'waiting' and excluded from
        the ready list. Only issues without dependencies or with all
        dependencies satisfied are returned.

        Args:
            raw_issues: Raw issue payloads from GitHub

        Returns:
            Filtered and sorted ready issues (excluding waiting)
        """
        selected: list[IssueInfo] = []
        for item in raw_issues:
            labels = _normalize_labels(item.get("labels"))
            if IssueState.BLOCKED.to_label() in labels:
                continue
            # Skip failed issues - they should not be auto-dispatched
            if IssueState.FAILED.to_label() in labels:
                continue
            if self.role_def.trigger_state.to_label() not in labels:
                continue
            issue = IssueInfo.from_github_payload(item)
            if issue is None:
                continue

            # Check for dependencies before proceeding
            dependencies = self._get_issue_dependencies(issue.number)
            if dependencies:
                # Has dependencies → check if all are satisfied
                unresolved = [
                    d for d in dependencies if not self._is_dependency_satisfied(d)
                ]

                if unresolved:
                    # Move to waiting state (not ready)
                    self._mark_issue_waiting(issue.number, unresolved)
                    logger.bind(
                        domain="orchestra",
                        dispatcher=self.service_name,
                        issue=issue.number,
                    ).info(
                        f"Issue #{issue.number} has unresolved dependencies: "
                        f"{unresolved}"
                    )
                    continue

            # No dependencies OR all satisfied → proceed with ready check
            if self.role_def.trigger_name == "manager":
                # Manager is the entry point. If the trigger label is present,
                # keep the issue in the frozen queue and let the coordinator
                # decide when to fire the next hop.
                selected.append(issue)
                continue

            # For downstream roles (plan/run/review), we need a branch to exist.
            branch, flow_state = self._flow_context(issue.number)
            if not branch or not _is_auto_task_branch(branch):
                # If no branch exists yet, we can't dispatch downstream agents.
                # This usually means manager hasn't run yet.
                continue

            # Verify the git branch actually exists, not just a stale flow record.
            # A flow may reference a branch that was deleted (aborted/cleaned up).
            if not self._flow_manager.git.branch_exists(branch):
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} skip #{issue.number}: "
                    f"branch '{branch}' not found in git",
                )
                continue

            selected.append(issue)
        return sort_ready_issues(selected)
