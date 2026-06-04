"""Orchestration facade - unified entry point for runtime observations.

将 runtime 层的观察转换为 domain events，纯 observation → publish 职责。
Governance 与 Supervisor Apply 的执行装配由各自的 domain handler 负责，
不在 facade 内内联。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.domain import publish
from vibe3.domain.events.governance import GovernanceScanStarted
from vibe3.models import IssueInfo
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.runtime import ServiceBase

if TYPE_CHECKING:
    from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.domain.failed_gate import FailedGate
    from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.execution.capacity_service import CapacityService


class OrchestrationFacade(ServiceBase):
    """Unified orchestration entry point.

    职责（纯 observation 层）：
    - 接受 runtime observations（issue state change、heartbeat tick、supervisor scan）
    - 发布对应的 domain events
    - 不做具体的链路 dispatch（由 domain handlers 负责）

    这是 Domain-first 架构的 observation 层，runtime 不直接决定链路行为，
    只发布事件；执行装配由订阅对应事件的 domain handler 完成。
    """

    def __init__(
        self,
        tick_count: int = 0,
        config: OrchestraConfig | None = None,
        capacity: "CapacityService | None" = None,
        failed_gate: "FailedGate | None" = None,
        store: "SQLiteClient | None" = None,
        github: "GitHubClient | None" = None,
        flow_manager: "FlowManagerProtocol | None" = None,
        registry: "SessionRegistryService | None" = None,
    ) -> None:
        """Initialize facade with tick counter.

        Args:
            tick_count: Initial tick count for governance scan tracking
            config: Runtime orchestra config. When omitted, falls back to
                settings-based defaults for tests and direct construction.
            capacity: Optional CapacityService for capacity-aware dispatch.
                When provided, GlobalDispatchCoordinator is used for unified
                dispatch with capacity checks before emitting intents.
                When None, legacy concurrent gather path is used (backward compat).
            failed_gate: Optional FailedGate retained for compatibility with
                existing server assembly. Runtime dispatch is no longer frozen
                here; gating belongs on the authoritative sync execution path.
            store: Optional SQLiteClient for dependency injection. When omitted
                with capacity provided, creates a new SQLiteClient instance.
            github: Optional GitHubClient for dependency injection. When omitted,
                creates a new GitHubClient instance.
            flow_manager: Optional FlowManager for dependency injection. When omitted,
                creates a new FlowManager instance with the provided config.
            registry: Optional SessionRegistryService for dependency injection.
                When omitted with capacity provided, creates a new
                SessionRegistryService instance. This enables reusing a shared
                registry instance across the facade's lifetime instead of
                creating a new one on each tick.
        """
        self._tick_count = tick_count
        self._governance_execution_count = (
            0  # Independent counter for material rotation
        )
        self._config = config or load_orchestra_config()
        self._created_at = time.monotonic()
        self._last_governance_started_at: float | None = None
        self._capacity = capacity
        self._coordinator: GlobalDispatchCoordinator | None = None
        self._failed_gate = failed_gate
        self._github = github or GitHubClient()
        from vibe3.domain import FlowManager

        self._flow_manager = flow_manager or FlowManager(self._config)
        self._registry: SessionRegistryService | None = registry

        if self._capacity is not None:
            from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
            from vibe3.environment.session_registry import SessionRegistryService
            from vibe3.orchestra.dispatch_health_check import DispatchHealthCheckService
            from vibe3.orchestra.issue_loader import get_flow_context, load_issue
            from vibe3.orchestra.queue_operations import (
                select_ready_issues_from_collected_issues,
            )
            from vibe3.orchestra.queue_persistence_service import (
                QueuePersistenceService,
            )
            from vibe3.services.check_service import CheckService
            from vibe3.services.flow_service import FlowService

            actual_store = store or SQLiteClient()
            self._registry = registry or SessionRegistryService(
                actual_store, self._capacity._backend
            )

            # Inject concrete service instances
            check_service = CheckService(
                store=actual_store,
                git_client=self._flow_manager.git,
                github_client=self._github,
            )
            flow_blocker = FlowService(
                store=actual_store,
                git_client=self._flow_manager.git,
            )

            # Construct runtime services for injection
            health_check_service = DispatchHealthCheckService(
                check_service=check_service,
                flow_blocker=flow_blocker,
                store=actual_store,
                flow_context_resolver=lambda n: get_flow_context(
                    n, self._config, self._github, actual_store, self._flow_manager
                ),
            )
            queue_persistence = QueuePersistenceService(
                store=actual_store,
                config=self._config,
                github=self._github,
                registry=self._registry,
                supervisor_label=self._config.supervisor_handoff.issue_label,
                load_issue=lambda n: load_issue(n, self._config, self._github),
            )

            self._coordinator = GlobalDispatchCoordinator(
                config=self._config,
                capacity=self._capacity,
                github=self._github,
                store=actual_store,
                flow_manager=self._flow_manager,
                registry=self._registry,
                health_check_service=health_check_service,
                queue_persistence=queue_persistence,
                issue_loader=lambda n: load_issue(n, self._config, self._github),
                flow_context_resolver=lambda n: get_flow_context(
                    n, self._config, self._github, actual_store, self._flow_manager
                ),
                queue_selector=select_ready_issues_from_collected_issues,
                check_service=check_service,
                flow_blocker=flow_blocker,
            )

    def shutdown(self) -> None:
        """Cleanup resources owned by the facade."""
        if self._coordinator:
            self._coordinator.shutdown()

    def get_queued_issue_numbers(self) -> set[int]:
        """Get issue numbers currently in the dispatch queue."""
        if self._coordinator:
            return self._coordinator.get_queued_issue_numbers()
        return set()

    async def on_tick(self, tick_id: int = 0) -> None:
        """Heartbeat polling -> publish governance + supervisor events.

        Called by runtime heartbeat periodically:
        1. Publishes GovernanceScanStarted (if interval gating passes)
        2. Publishes SupervisorIssueIdentified for matching issues
        3. Reconciles in-flight markers (always, even when frozen)
        4. Polls issue labels and dispatches (only when not frozen)

        Args:
            tick_id: Current tick number from HeartbeatServer (default: 0)
        """
        from vibe3.observability.orchestra_log import append_orchestra_event

        self.on_heartbeat_tick()

        # Check failed gate before any dispatch (supervisor included)
        if self._failed_gate is not None:
            gate_result = self._failed_gate.check()
            if gate_result.blocked:
                reason_part = (
                    f" reason={gate_result.reason}" if gate_result.reason else ""
                )
                append_orchestra_event(
                    "dispatcher",
                    f"dispatch blocked by failed gate:{reason_part}",
                )
                logger.bind(
                    domain="orchestration_facade",
                    reason=gate_result.reason,
                    blocked_ticks=gate_result.blocked_ticks,
                ).warning("Dispatch blocked by failed gate")
                self._failed_gate.increment_blocked_ticks()
                return

        # Scan for supervisor candidates and publish events
        try:
            await self.on_supervisor_scan()
        except Exception as exc:
            append_orchestra_event(
                "server",
                f"tick #{self._tick_count} supervisor scan failed: {exc}",
            )
            logger.bind(domain="orchestration_facade").error(
                f"Supervisor scan failed: {exc}"
            )
            # Continue to dispatch even if supervisor scan fails

        # Poll issue labels for all trigger states
        if self._coordinator is None:
            logger.bind(
                domain="orchestration_facade",
            ).warning(
                "GlobalDispatchCoordinator not initialized, dispatch skipped "
                "(capacity not provided)"
            )
            return

        # Always reconcile session state to prevent stale capacity tracking.
        if self._capacity:
            # Type guard: registry is guaranteed non-None when capacity exists
            assert self._registry is not None
            try:
                # Reconcile session state (mark dead tmux sessions as orphaned)
                # This ensures count_live_worker_sessions() returns accurate results.
                # Uses the registry instance from constructor injection instead of
                # creating a new SQLiteClient + SessionRegistryService per tick.
                self._registry.mark_worker_sessions_done_when_tmux_gone()
                self._registry.reconcile_live_state()
            except Exception as exc:
                append_orchestra_event(
                    "server",
                    f"tick #{self._tick_count} session reconciliation failed: {exc}",
                )
                logger.bind(domain="orchestration_facade").error(
                    f"Session reconciliation failed: {exc}"
                )
                # Continue to dispatch even if reconciliation fails

        await self._coordinator.coordinate(tick_id)

    def on_heartbeat_tick(self) -> None:
        """Heartbeat polling -> 发布 GovernanceScanStarted 事件.

        由 runtime heartbeat 定期调用，发布 governance 链路的 periodic scan 事件。
        包含 interval_ticks gating，避免每次 tick 都触发。

        注意：此方法仅供自动 heartbeat polling 使用。
        Manual governance scan 不走此路径，直接调用 service layer。
        """
        self._tick_count += 1
        tick_count = self._tick_count

        # Apply interval gating (e.g., run every 5 ticks)
        interval = self._config.governance.interval_ticks
        if tick_count % interval != 0:
            logger.bind(
                domain="orchestration_facade",
                tick_count=tick_count,
                interval=interval,
            ).debug(
                f"Skipping governance scan (tick {tick_count} "
                f"not divisible by {interval})"
            )
            return

        # Apply time-based gating (minimum seconds between scans)
        min_interval_seconds = self._config.polling_interval * interval
        now = time.monotonic()
        last_started_at = self._last_governance_started_at or self._created_at
        elapsed = now - last_started_at
        if elapsed < min_interval_seconds:
            logger.bind(
                domain="orchestration_facade",
                tick_count=tick_count,
                interval=interval,
                min_interval_seconds=min_interval_seconds,
                elapsed_seconds=round(elapsed, 2),
            ).debug("Skipping governance scan (min interval not reached)")
            return

        # Update timestamp when actually emitting event
        self._last_governance_started_at = time.monotonic()

        # Increment governance execution count for material rotation
        self._governance_execution_count += 1

        event = GovernanceScanStarted(
            tick_count=tick_count, execution_count=self._governance_execution_count
        )
        logger.bind(
            domain="orchestration_facade",
            tick_count=tick_count,
            execution_count=self._governance_execution_count,
        ).info("Emitting GovernanceScanStarted event")
        publish(event)

    def on_governance_decision(
        self,
        issue_info: IssueInfo,
        reason: str,
        suggested_action: str | None = None,
    ) -> None:
        """Governance 发现需要决策的 issue -> 直接 post GitHub comment.

        Args:
            issue_info: Issue 信息（包含需要决策的 issue 详情）
            reason: Reason for the decision requirement
            suggested_action: Optional suggested action
        """
        logger.bind(
            domain="orchestration_facade",
            issue_number=issue_info.number,
            reason=reason,
        ).warning("Governance decision required")

        comment_body = f"## Governance Decision Required\n\n**Reason**: {reason}\n\n"
        if suggested_action:
            comment_body += f"**Suggested Action**: {suggested_action}\n\n"

        self._github.add_comment(issue_info.number, comment_body)

    async def on_supervisor_scan(self) -> tuple[int, int]:
        """扫描 supervisor candidates 并发布 SupervisorIssueIdentified 事件.

        查找带有 supervisor + state/handoff labels 的 issues，
        发布 SupervisorIssueIdentified 事件。
        包含 interval_ticks gating，避免每 tick 都触发（与 governance 同频）。
        执行装配由 supervisor_scan handler 负责，facade 只做 observation。

        Returns:
            Tuple of (total_issues_scanned, matched_issues_found)
        """
        interval = self._config.supervisor_handoff.interval_ticks
        if self._tick_count % interval != 0:
            logger.bind(
                domain="orchestration_facade",
                tick_count=self._tick_count,
                interval=interval,
            ).debug(
                f"Skipping supervisor scan (tick {self._tick_count} "
                f"not divisible by {interval})"
            )
            return (0, 0)

        from vibe3.roles.supervisor import iter_supervisor_identified_events

        config = self._config

        raw_issues = self._github.list_issues(
            limit=100,
            state="open",
            assignee=None,
            repo=config.repo,
        )

        total_scanned = len(raw_issues)
        events = list(iter_supervisor_identified_events(config, raw_issues))
        matched_count = len(events)

        for event in events:
            logger.bind(
                domain="orchestration_facade",
                issue_number=event.issue_number,
                supervisor_file=event.supervisor_file,
            ).info("Supervisor candidate found, publishing SupervisorIssueIdentified")
            publish(event)

        return (total_scanned, matched_count)
