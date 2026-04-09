"""Orchestration facade - unified entry point for runtime observations.

将 runtime 层的观察转换为 domain events，由 domain handlers 处理具体链路逻辑。
"""

import asyncio
import time
from collections.abc import Sequence

from loguru import logger

from vibe3.domain import publish
from vibe3.domain.events import (
    ExecutorDispatched,
    GovernanceDecisionRequired,
    GovernanceScanStarted,
    IssueStateChanged,
    PlannerDispatched,
    ReviewerDispatched,
    SupervisorIssueIdentified,
)
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo
from vibe3.orchestra.logging import append_orchestra_event
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase


class OrchestrationFacade(ServiceBase):
    """Unified orchestration entry point.

    职责：
    - 接受 runtime observations（如 issue state change、heartbeat tick）
    - 发布对应的 domain events
    - 不做具体的链路 dispatch（由 domain handlers 负责）

    这是 Domain-first 的第一步，runtime 不直接决定链路行为，只发布事件。
    """

    event_types = ["issues"]

    def __init__(
        self,
        tick_count: int = 0,
        dispatch_services: Sequence[ServiceBase] | None = None,
    ) -> None:
        """Initialize facade with tick counter.

        Args:
            tick_count: Initial tick count for governance scan tracking
            dispatch_services: Optional list of issue-polling dispatch services
                (StateLabelDispatchService instances). When provided, their
                on_tick() methods are called concurrently from this facade's
                on_tick(), replacing the need to register them separately in
                the heartbeat server.
        """
        self._tick_count = tick_count
        self._config = OrchestraConfig.from_settings()
        self._created_at = time.monotonic()
        self._last_governance_started_at: float | None = None
        self._dispatch_services = list(dispatch_services or [])

    async def on_tick(self) -> None:
        """Heartbeat polling -> trigger governance scan and issue dispatch.

        Called by runtime heartbeat periodically:
        1. Emits GovernanceScanStarted for governance chain
        2. Scans for supervisor candidates
        3. Polls issue labels for all dispatch services (replaces separate
           StateLabelDispatchService heartbeat registrations)
        """
        self.on_heartbeat_tick()

        # Scan for supervisor candidates
        await self.on_supervisor_scan()

        # Poll issue labels for all trigger states concurrently
        if self._dispatch_services:
            await self._run_dispatch_services()

    async def _run_dispatch_services(self) -> None:
        """Run all dispatch services and surface failures in orchestra logs."""
        results = await asyncio.gather(
            *(service.on_tick() for service in self._dispatch_services),
            return_exceptions=True,
        )
        for service, result in zip(self._dispatch_services, results, strict=False):
            if not isinstance(result, Exception):
                continue
            append_orchestra_event(
                "server",
                f"tick error in {service.service_name}: {result}",
            )
            logger.bind(
                domain="orchestration_facade",
                service=service.service_name,
            ).error(f"Dispatch service tick failed: {result}")

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
        """Runtime 观察到 issue 状态变化 -> 发布事件.

        Args:
            issue_info: Issue 信息（包含 number、state 等）
            from_state: Previous state (optional, can be inferred)
        """
        # Convert IssueState enum to string if needed
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

        publish(event)

    def on_heartbeat_tick(self) -> None:
        """Heartbeat polling -> 触发 governance scan.

        由 runtime heartbeat 定期调用，触发 governance 链路的 periodic scan。
        包含 interval_ticks gating，避免每次 tick 都扫描。
        """
        self._tick_count += 1

        # Apply interval_ticks gating
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

        event = GovernanceScanStarted(tick_count=self._tick_count)
        self._last_governance_started_at = now

        logger.bind(
            domain="orchestration_facade",
            tick_count=self._tick_count,
        ).info("Emitting GovernanceScanStarted event")

        publish(event)

    def on_governance_decision(
        self,
        issue_info: IssueInfo,
        reason: str,
        suggested_action: str | None = None,
    ) -> None:
        """Governance 发现需要决策的 issue -> 发布决策事件.

        Args:
            issue_info: Issue 信息（包含需要决策的 issue 详情）
            reason: Reason for the decision requirement
            suggested_action: Optional suggested action
        """
        event = GovernanceDecisionRequired(
            issue_number=issue_info.number,
            reason=reason,
            suggested_action=suggested_action,
        )

        logger.bind(
            domain="orchestration_facade",
            issue_number=issue_info.number,
        ).info("Emitting GovernanceDecisionRequired event")

        publish(event)

    def on_planner_dispatch(
        self,
        issue_info: IssueInfo,
        branch: str,
    ) -> None:
        """发布 planner dispatch-intent 事件.

        Args:
            issue_info: Issue 信息
            branch: 目标分支
        """
        event = PlannerDispatched(
            issue_number=issue_info.number,
            branch=branch,
            trigger_state="claimed",
        )

        logger.bind(
            domain="orchestration_facade",
            issue_number=issue_info.number,
            branch=branch,
        ).info("Emitting PlannerDispatched event")

        publish(event)

    def on_executor_dispatch(
        self,
        issue_info: IssueInfo,
        branch: str,
        plan_ref: str | None = None,
    ) -> None:
        """发布 executor dispatch-intent 事件.

        Args:
            issue_info: Issue 信息
            branch: 目标分支
            plan_ref: Plan reference (optional)
        """
        event = ExecutorDispatched(
            issue_number=issue_info.number,
            branch=branch,
            trigger_state="in-progress",
            plan_ref=plan_ref,
        )

        logger.bind(
            domain="orchestration_facade",
            issue_number=issue_info.number,
            branch=branch,
        ).info("Emitting ExecutorDispatched event")

        publish(event)

    def on_reviewer_dispatch(
        self,
        issue_info: IssueInfo,
        branch: str,
        report_ref: str | None = None,
    ) -> None:
        """发布 reviewer dispatch-intent 事件.

        Args:
            issue_info: Issue 信息
            branch: 目标分支
            report_ref: Report reference (optional)
        """
        event = ReviewerDispatched(
            issue_number=issue_info.number,
            branch=branch,
            trigger_state="review",
            report_ref=report_ref,
        )

        logger.bind(
            domain="orchestration_facade",
            issue_number=issue_info.number,
            branch=branch,
        ).info("Emitting ReviewerDispatched event")

        publish(event)

    async def on_supervisor_scan(self) -> None:
        """扫描并发布 supervisor candidates.

        查找带有 supervisor + state/handoff labels 的 issues，
        发布 SupervisorIssueIdentified 事件。
        """
        from vibe3.clients.github_client import GitHubClient

        github = GitHubClient()
        config = self._config

        # List issues with supervisor + state/handoff labels
        raw_issues = github.list_issues(
            limit=100,
            state="open",
            assignee=None,
            repo=config.repo,
        )

        issue_label = config.supervisor_handoff.issue_label
        handoff_label = config.supervisor_handoff.handoff_state_label

        for item in raw_issues:
            number = item.get("number")
            title = item.get("title")
            if not isinstance(number, int) or not isinstance(title, str):
                continue

            labels_raw = item.get("labels", [])
            labels = []
            if isinstance(labels_raw, list):
                for lbl in labels_raw:
                    if isinstance(lbl, dict):
                        name = lbl.get("name")
                        if isinstance(name, str):
                            labels.append(name)

            # Check if issue has both supervisor and state/handoff labels
            if issue_label not in labels or handoff_label not in labels:
                continue

            # Emit SupervisorIssueIdentified event
            supervisor_file = config.supervisor_handoff.supervisor_file
            event = SupervisorIssueIdentified(
                issue_number=number,
                issue_title=title,
                supervisor_file=supervisor_file,
            )

            logger.bind(
                domain="orchestration_facade",
                issue_number=number,
                supervisor_file=supervisor_file,
            ).info("Emitting SupervisorIssueIdentified event")

            publish(event)
