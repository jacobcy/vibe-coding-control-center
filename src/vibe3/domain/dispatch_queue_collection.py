"""Frozen-queue collection service for GlobalDispatchCoordinator.

Extracted from dispatch_coordinator.py to manage file size while keeping
queue collection operations accessible from coordinate().
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Callable

from loguru import logger

from vibe3.domain.qualify_gate import QualifyGateService
from vibe3.models import IssueInfo, IssueState, OrchestraConfig, QueueEntry

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.domain.protocols.dispatch_protocols import (
        IssueCollectionServiceProtocol,
        QueueSelectorProtocol,
    )
    from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol


def _is_executor_shutdown_error(exc: RuntimeError) -> bool:
    """Check if a RuntimeError indicates executor shutdown.

    In CPython 3.12, ThreadPoolExecutor.submit() raises RuntimeError with
    message "cannot schedule new futures after shutdown" after shutdown()
    is called. This helper detects such errors for graceful degradation.
    """
    msg = str(exc).lower()
    return "shutdown" in msg or "cannot schedule" in msg


class DispatchQueueCollectionService:
    """Queue collection operations that require GitHub API calls.

    Handles the full lifecycle of collecting issues from GitHub,
    building a queue from them, and requalifying blocked issues.
    Used by GlobalDispatchCoordinator during queue refresh cycles.
    """

    def __init__(
        self,
        config: OrchestraConfig,
        github: "GitHubClient",
        store: "SQLiteClient",
        flow_manager: "FlowManagerProtocol",
        executor: ThreadPoolExecutor,
        issue_collector_factory: "Callable[[], IssueCollectionServiceProtocol]",
        queue_selector: "QueueSelectorProtocol",
        qualify_gate: QualifyGateService,
        supervisor_label: str,
        emit_event: "Callable[[str, str], None]",
        queue_filter: "Callable[..., bool] | None" = None,
    ) -> None:
        self._config = config
        self._github = github
        self._store = store
        self._flow_manager = flow_manager
        self._executor = executor
        self._issue_collector_factory = issue_collector_factory
        self._queue_selector = queue_selector
        self._qualify_gate = qualify_gate
        self._supervisor_label = supervisor_label
        self._emit_event = emit_event
        self._queue_filter = queue_filter

    def collect_open_issues(self) -> list[IssueInfo]:
        """Phase 1: Single open-issue collection pass.

        One GitHub API call via IssueCollectionService.
        Returns empty list on failure (fail-safe).

        Note: This method is synchronous and intended to be run in an executor
        to avoid blocking the async event loop.
        """
        try:
            return self._issue_collector_factory().collect_open_issues()
        except Exception as exc:
            self._emit_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: collect_open_issues failed: {exc}",
            )
            logger.bind(domain="global_dispatch").error(
                f"collect_open_issues failed: {exc}"
            )
            return []

    def build_queue_from_issues(
        self, collected_issues: list[IssueInfo]
    ) -> list[QueueEntry]:
        """Phase 2: Filter and order candidates with state-first ordering.

        Iterates through state groups in priority order:
        REVIEW -> MERGE_READY -> IN_PROGRESS -> CLAIMED -> HANDOFF -> READY

        Within each state group, issues are ordered by:
        milestone -> roadmap rank -> priority -> issue number

        Args:
            collected_issues: List of issues from open-issue collection

        Returns:
            List of QueueEntry objects in state-first order
        """
        queue: list[QueueEntry] = []
        seen_issue_numbers: set[int] = set()

        for state in (
            IssueState.REVIEW,
            IssueState.MERGE_READY,
            IssueState.IN_PROGRESS,
            IssueState.CLAIMED,
            IssueState.HANDOFF,
            IssueState.READY,
        ):
            try:
                issues = self._queue_selector(
                    collected_issues,
                    state,
                    self._config,
                    self._github,
                    self._store,
                    self._flow_manager,
                    self._qualify_gate,
                    self._supervisor_label,
                    queue_filter=self._queue_filter,
                )
                for issue in issues:
                    if issue.number in seen_issue_numbers:
                        continue
                    seen_issue_numbers.add(issue.number)
                    queue.append(
                        QueueEntry(
                            issue_number=issue.number,
                            collected_state=state.value,
                        )
                    )
            except Exception as exc:
                self._emit_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: collect_ready_issues failed for "
                    f"{state.value}: {exc}",
                )
                logger.bind(
                    domain="global_dispatch",
                    state=state.value,
                ).error(
                    "select_ready_issues_from_collected_issues failed for "
                    f"{state.value}: {exc}"
                )

        if queue:
            self._emit_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: queue collection complete, "
                f"total={len(queue)} issues",
            )
        return queue

    def requalify_blocked_issues(self, collected_issues: list[IssueInfo]) -> None:
        """Re-run the qualify gate for issues collected as BLOCKED.

        BLOCKED issues are excluded from the frozen queue (they cannot be
        dispatched), so without this pass an issue whose blockers have
        resolved would never be re-qualified until some other trigger
        forces a collection. ``qualify_blocked_issue`` performs its own
        label transition and event logging when an issue becomes
        resumable; the relabeled issue is then picked up normally on the
        next collection cycle.

        Dependency Resolution Routing:
            qualify_blocked_issue -> is_dependency_satisfied ->
            DependencyResolutionService.is_dependency_resolved()

        This centralized routing ensures consistent dependency checking
        across all code paths (dispatch, resume, consistency checks).
        """
        for issue in collected_issues:
            if issue.state != IssueState.BLOCKED:
                continue
            try:
                self._qualify_gate.qualify_blocked_issue(issue)
            except Exception as exc:
                self._emit_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: requalify failed for "
                    f"#{issue.number}: {exc}",
                )
                logger.bind(
                    domain="global_dispatch",
                    issue=issue.number,
                ).warning(f"qualify_blocked_issue failed for #{issue.number}: {exc}")

    async def collect_frozen_queue(self) -> list[QueueEntry]:
        """Full frozen queue collection with explicit phases.

        Phases:
          1. Collect -- Single open-issue pass via IssueCollectionService
          2. Filter & Order -- State-group iteration with state-first ordering
          3. Re-qualify -- Blocked issue dependency requalification

        See build_queue_from_issues for ordering semantics.

        Exception Handling:
            API failures within collect_open_issues (GitHub errors, network
            issues) return an empty list (fail-safe). Infrastructure failures
            (executor shutdown, thread pool exhaustion) are also handled
            gracefully by returning an empty list with logging and orchestra
            events, allowing the dispatch tick to continue without permanent
            failure.

        Returns:
            List of QueueEntry objects ready for dispatch
        """
        try:
            collected_issues = await asyncio.get_running_loop().run_in_executor(
                self._executor,
                self.collect_open_issues,
            )
        except RuntimeError as exc:
            if _is_executor_shutdown_error(exc):
                self._emit_event(
                    "dispatcher",
                    f"GlobalDispatchCoordinator: executor shutdown during "
                    f"frozen queue collection: {exc}",
                )
                logger.bind(domain="global_dispatch").error(
                    f"_collect_frozen_queue executor unavailable: {exc}"
                )
                return []
            raise
        except asyncio.CancelledError:
            self._emit_event(
                "dispatcher",
                "GlobalDispatchCoordinator: cancelled during frozen queue collection",
            )
            logger.bind(domain="global_dispatch").warning(
                "_collect_frozen_queue cancelled"
            )
            return []
        except Exception as exc:
            self._emit_event(
                "dispatcher",
                f"GlobalDispatchCoordinator: unexpected infrastructure error "
                f"during frozen queue collection: {exc}",
            )
            logger.bind(domain="global_dispatch").error(
                f"_collect_frozen_queue unexpected error: {exc}"
            )
            return []

        queue = self.build_queue_from_issues(collected_issues)
        self.requalify_blocked_issues(collected_issues)
        return queue
