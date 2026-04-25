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
from vibe3.services.flow_resume_resolver import infer_resume_label
from vibe3.utils.label_utils import should_skip_from_queue

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

        Also polls state/blocked issues to perform automatic unblocking.

        Returns:
            Filtered and sorted ready issues list.
        """
        async with self._dispatch_guard:
            # Poll issues matching this role's trigger state
            trigger_issues = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self._github.list_issues(
                    limit=100,
                    state="open",
                    assignee=None,
                    repo=self.config.repo,
                    label=self.role_def.trigger_state.to_label(),
                ),
            )
            # ALSO poll blocked issues for this dispatcher to perform patrol
            blocked_issues = await asyncio.get_event_loop().run_in_executor(
                self._executor,
                lambda: self._github.list_issues(
                    limit=100,
                    state="open",
                    assignee=None,
                    repo=self.config.repo,
                    label=IssueState.BLOCKED.to_label(),
                ),
            )

            # Merge and deduplicate
            raw_issues_map = {item["number"]: item for item in trigger_issues}
            for item in blocked_issues:
                raw_issues_map[item["number"]] = item
            raw_issues = list(raw_issues_map.values())

            ready = self._select_ready_issues(raw_issues)

            append_orchestra_event(
                "dispatcher",
                f"{self.service_name} collect: {len(ready)} ready issues",
            )
            return ready

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

    def _select_ready_issues(
        self, raw_issues: list[dict[str, object]]
    ) -> list[IssueInfo]:
        """Select ready issues by passing them through the Qualify Gate.

        Args:
            raw_issues: Raw issue payloads from GitHub

        Returns:
            Filtered and sorted ready issues
        """
        selected: list[IssueInfo] = []
        for item in raw_issues:
            labels = _normalize_labels(item.get("labels"))

            # Untracked state: ignore issues with no state labels
            if not any(lbl.startswith("state/") for lbl in labels):
                continue

            # Skip failed issues
            if IssueState.FAILED.to_label() in labels:
                continue

            issue = IssueInfo.from_github_payload(item)
            if issue is None:
                continue

            branch, flow_state = self._flow_context(issue.number)

            # Qualify Gate
            if not self._run_qualify_gate(issue, branch, flow_state, labels):
                continue

            # Role-specific branch existence requirements
            if self.role_def.trigger_name != "manager":
                if not branch or not _is_auto_task_branch(branch):
                    continue
                if not self._flow_manager.git.branch_exists(branch):
                    append_orchestra_event(
                        "dispatcher",
                        f"{self.service_name} skip #{issue.number}: "
                        f"branch '{branch}' not found in git",
                    )
                    continue

            # Verify assignee/supervisor filters
            if should_skip_from_queue(
                issue,
                supervisor_label=self.config.supervisor_handoff.issue_label,
                manager_usernames=self.config.manager_usernames,
                require_manager_assignee=(
                    self.role_def.trigger_state == IssueState.READY
                ),
            ):
                continue

            selected.append(issue)

        return sort_ready_issues(selected)

    def _run_qualify_gate(
        self,
        issue: IssueInfo,
        branch: str,
        flow_state: dict[str, object] | None,
        labels: list[str],
    ) -> bool:
        """Run the Qualify Gate for an issue to resolve dependencies and blocking.

        Returns:
            True if the issue passes the gate and should be dispatched by
            THIS dispatcher.
        """
        if not flow_state:
            if IssueState.BLOCKED.to_label() in labels:
                # Local state missing but remote is blocked -> skip
                append_orchestra_event(
                    "dispatcher",
                    f"{self.service_name} skip #{issue.number}: "
                    "local flow state missing but remote is blocked",
                )
                return False
            # For manager entry point on new issues
            return self.role_def.trigger_state.to_label() in labels

        # Step 1: Check manual block
        blocked_reason = flow_state.get("blocked_reason")
        if blocked_reason and str(blocked_reason).strip():
            # Missing remote blocked label but locally blocked manually
            if IssueState.BLOCKED.to_label() not in labels:
                try:
                    label_port = GhIssueLabelPort(repo=self.config.repo)
                    label_port.add_issue_label(issue.number, "state/blocked")
                except Exception as exc:
                    logger.bind(domain="orchestra").warning(
                        f"Failed to add state/blocked: {exc}"
                    )
            return False

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
                    flow_status="blocked",
                    blocked_by_issue=unresolved[0],
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
            return False

        # Step 3: Automatic unblock and dispatch
        from vibe3.models.flow import FlowState

        fs_obj = FlowState.model_validate(flow_state)
        target_label = infer_resume_label(fs_obj)

        unblocked = False
        if flow_state.get("blocked_by_issue"):
            dep_issue = flow_state.get("blocked_by_issue")
            source_pr = None
            if isinstance(dep_issue, int):
                dep_flows = self._store.get_flows_by_issue(dep_issue, role="task")
                for df in dep_flows:
                    if df.get("pr_number"):
                        source_pr = df.get("pr_number")
                        break

            refs = {}
            if source_pr:
                refs["source_pr"] = str(source_pr)

            self._store.update_flow_state(
                branch,
                flow_status=target_label.value,
                blocked_by_issue=None,
            )
            self._store.add_event(
                branch,
                "flow_unblocked",
                "orchestra:dispatcher",
                detail=f"Dependencies satisfied, target: {target_label.value}",
                refs=refs if refs else None,
            )
            unblocked = True

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
            unblocked = True

        # H3: If we just unblocked, skip dispatch in this tick.
        # This allows the unblocked labels to propagate and avoids
        # race conditions/ambiguous dispatcher states.
        if unblocked:
            return False

        # If no unblock happened, just check if the label matches our trigger state.
        return self.role_def.trigger_state.to_label() in labels
