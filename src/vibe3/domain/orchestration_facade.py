"""Orchestration facade - unified entry point for runtime observations.

将 runtime 层的观察转换为 domain events，纯 observation → publish 职责。
Governance 与 Supervisor Apply 的执行装配由各自的 domain handler 负责，
不在 facade 内内联。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.domain import publish
from vibe3.domain.events.flow_lifecycle import IssueStateChanged
from vibe3.domain.events.governance import GovernanceScanStarted
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo
from vibe3.runtime.service_protocol import GitHubEvent, ServiceBase

if TYPE_CHECKING:
    from vibe3.execution.capacity_service import CapacityService
    from vibe3.orchestra.failed_gate import FailedGate
    from vibe3.orchestra.global_dispatch_coordinator import GlobalDispatchCoordinator
    from vibe3.orchestra.services.state_label_dispatch import StateLabelDispatchService


class OrchestrationFacade(ServiceBase):
    """Unified orchestration entry point.

    职责（纯 observation 层）：
    - 接受 runtime observations（issue state change、heartbeat tick、supervisor scan）
    - 发布对应的 domain events
    - 不做具体的链路 dispatch（由 domain handlers 负责）

    这是 Domain-first 架构的 observation 层，runtime 不直接决定链路行为，
    只发布事件；执行装配由订阅对应事件的 domain handler 完成。
    """

    event_types = ["issues"]

    def __init__(
        self,
        tick_count: int = 0,
        dispatch_services: list[StateLabelDispatchService] | None = None,
        capacity: CapacityService | None = None,
        failed_gate: "FailedGate | None" = None,
    ) -> None:
        """Initialize facade with tick counter.

        Args:
            tick_count: Initial tick count for governance scan tracking
            dispatch_services: Optional list of issue-polling dispatch services
                (StateLabelDispatchService instances). When provided, their
                on_tick() methods are called concurrently from this facade's
                on_tick(), replacing the need to register them separately in
                the heartbeat server.
            capacity: Optional CapacityService for capacity-aware dispatch.
                When provided, GlobalDispatchCoordinator is used for unified
                dispatch with capacity checks before emitting intents.
                When None, legacy concurrent gather path is used (backward compat).
            failed_gate: Optional FailedGate to check if dispatch is frozen.
                When provided, on_tick() checks gate before dispatch but
                always reconciles in-flight markers to prevent capacity deadlock.
        """
        self._tick_count = tick_count
        self._config = OrchestraConfig.from_settings()
        self._created_at = time.monotonic()
        self._last_governance_started_at: float | None = None
        self._dispatch_services = list(dispatch_services or [])
        self._capacity = capacity
        self._coordinator: GlobalDispatchCoordinator | None = None
        self._failed_gate = failed_gate

        if self._dispatch_services and self._capacity is not None:
            from vibe3.orchestra.global_dispatch_coordinator import (
                GlobalDispatchCoordinator,
            )

            self._coordinator = GlobalDispatchCoordinator(
                capacity=self._capacity,
                dispatch_services=self._dispatch_services,
            )

    async def on_tick(self) -> None:
        """Heartbeat polling -> publish governance + supervisor events.

        Called by runtime heartbeat periodically:
        1. Publishes GovernanceScanStarted (if interval gating passes)
        2. Publishes SupervisorIssueIdentified for matching issues
        3. Reconciles in-flight markers (always, even when frozen)
        4. Polls issue labels and dispatches (only when not frozen)
        """

        self.on_heartbeat_tick()

        # Scan for supervisor candidates and publish events
        await self.on_supervisor_scan()

        # Poll issue labels for all trigger states
        if not self._dispatch_services:
            return

        if self._coordinator is None:
            raise RuntimeError(
                "OrchestrationFacade: GlobalDispatchCoordinator not initialized. "
                "Both dispatch_services and capacity must be provided at init time."
            )

        # ✅ Always reconcile in-flight markers to prevent capacity deadlock
        # This must happen even when failed_gate is frozen
        if self._capacity:
            self._capacity.reconcile_in_flight()

        # Check if dispatch is frozen by failed gate
        if self._failed_gate:
            gate_result = self._failed_gate.check()
            if gate_result.blocked:
                logger.bind(
                    domain="orchestration_facade",
                    action="dispatch_frozen",
                    issue=gate_result.issue_number,
                ).info(
                    f"Dispatch frozen by state/failed issue "
                    f"#{gate_result.issue_number}, skipping collection and dispatch"
                )
                return

        await self._coordinator.coordinate()

    async def handle_event(self, event: GitHubEvent) -> None:
        """React to a GitHub event.

        Converts GitHub webhook/poll events to domain events.

        Args:
            event: GitHub event from webhook or polling
        """
        if event.event_type != "issues":
            return

        logger.bind(
            domain="orchestration_facade",
            event_type=event.event_type,
            action=event.action,
        ).debug(f"Received GitHub event: {event.event_type}.{event.action}")

        issue_payload = event.payload.get("issue")
        if not isinstance(issue_payload, dict):
            return

        issue_info = IssueInfo.from_github_payload(issue_payload)
        if issue_info is None or issue_info.state is None:
            return

        self.on_issue_state_changed(issue_info)

    def on_issue_state_changed(
        self,
        issue_info: IssueInfo,
        from_state: str | None = None,
    ) -> None:
        """Runtime 观察到 issue 状态变化 -> 发布 IssueStateChanged 事件.

        Args:
            issue_info: Issue 信息（包含 number、state 等）
            from_state: Previous state (optional, can be inferred)
        """
        to_state = (
            issue_info.state
            if isinstance(issue_info.state, str)
            else str(issue_info.state.value) if issue_info.state else ""
        )

        event = IssueStateChanged(
            issue_number=issue_info.number,
            from_state=from_state,
            to_state=to_state,
            issue_title=issue_info.title if issue_info.title else None,
        )

        logger.bind(
            domain="orchestration_facade",
            issue_number=issue_info.number,
            from_state=from_state,
            to_state=to_state,
        ).info("Emitting IssueStateChanged event")

        publish(event)  # type: ignore[no-untyped-call]

    def on_heartbeat_tick(self) -> None:
        """Heartbeat polling -> 发布 GovernanceScanStarted 事件.

        由 runtime heartbeat 定期调用，发布 governance 链路的 periodic scan 事件。
        包含 interval_ticks gating，避免每次 tick 都触发。
        执行装配由 governance_scan handler 负责，facade 只做 observation。
        """
        self._tick_count += 1

        interval = self._config.governance.interval_ticks
        if self._tick_count % interval != 0:
            logger.bind(
                domain="orchestration_facade",
                tick_count=self._tick_count,
                interval=interval,
            ).debug(
                f"Skipping governance scan (tick {self._tick_count} "
                f"not divisible by {interval})"
            )
            return

        min_interval_seconds = self._config.polling_interval * interval
        now = time.monotonic()
        last_started_at = self._last_governance_started_at or self._created_at
        elapsed = now - last_started_at
        if elapsed < min_interval_seconds:
            logger.bind(
                domain="orchestration_facade",
                tick_count=self._tick_count,
                interval=interval,
                min_interval_seconds=min_interval_seconds,
                elapsed_seconds=round(elapsed, 2),
            ).debug("Skipping governance scan (min interval not reached)")
            return

        self._last_governance_started_at = now

        event = GovernanceScanStarted(tick_count=self._tick_count)
        logger.bind(
            domain="orchestration_facade",
            tick_count=self._tick_count,
        ).info("Emitting GovernanceScanStarted event")
        publish(event)  # type: ignore[no-untyped-call]

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
        from vibe3.clients.github_client import GitHubClient

        logger.bind(
            domain="orchestration_facade",
            issue_number=issue_info.number,
            reason=reason,
        ).warning("Governance decision required")

        comment_body = f"## Governance Decision Required\n\n**Reason**: {reason}\n\n"
        if suggested_action:
            comment_body += f"**Suggested Action**: {suggested_action}\n\n"

        GitHubClient().add_comment(issue_info.number, comment_body)

    async def on_supervisor_scan(self) -> None:
        """扫描 supervisor candidates 并发布 SupervisorIssueIdentified 事件.

        查找带有 supervisor + state/handoff labels 的 issues，
        发布 SupervisorIssueIdentified 事件。
        执行装配由 supervisor_scan handler 负责，facade 只做 observation。
        """
        from vibe3.clients.github_client import GitHubClient
        from vibe3.roles.supervisor import iter_supervisor_identified_events

        github = GitHubClient()
        config = self._config

        raw_issues = github.list_issues(
            limit=100,
            state="open",
            assignee=None,
            repo=config.repo,
        )

        for event in iter_supervisor_identified_events(config, raw_issues):
            logger.bind(
                domain="orchestration_facade",
                issue_number=event.issue_number,
                supervisor_file=event.supervisor_file,
            ).info("Supervisor candidate found, publishing SupervisorIssueIdentified")
            publish(event)  # type: ignore[no-untyped-call]
