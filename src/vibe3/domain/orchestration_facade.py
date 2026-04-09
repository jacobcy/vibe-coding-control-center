"""Orchestration facade - unified entry point for runtime observations.

将 runtime 层的观察转换为 domain events，由 domain handlers 处理具体链路逻辑。
"""

from loguru import logger

from vibe3.domain import publish
from vibe3.domain.events import (
    GovernanceDecisionRequired,
    GovernanceScanStarted,
    IssueStateChanged,
)
from vibe3.models.orchestration import IssueInfo
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase


class OrchestrationFacade(ServiceBase):
    """Unified orchestration entry point.

    职责：
    - 接受 runtime observations（如 issue state change、heartbeat tick）
    - 发布对应的 domain events
    - 不做具体的链路 dispatch（由 domain handlers 负责）

    这是 Domain-first 的第一步，runtime 不直接决定链路行为，只发布事件。
    """

    def __init__(self, tick_count: int = 0) -> None:
        """Initialize facade with tick counter.

        Args:
            tick_count: Initial tick count for governance scan tracking
        """
        self._tick_count = tick_count

    async def on_tick(self) -> None:
        """Heartbeat polling -> trigger governance scan.

        Called by runtime heartbeat periodically, triggering governance chain.
        """
        self.on_heartbeat_tick()

    async def handle_event(self, event: GitHubEvent) -> None:
        """React to a GitHub event.

        Converts GitHub webhook/poll events to domain events.

        Args:
            event: GitHub event from webhook or polling
        """
        # TODO: Convert GitHub event to appropriate domain event
        # For now, just log the event
        logger.bind(
            domain="orchestration_facade",
            event_type=event.event_type,
            action=event.action,
        ).debug(f"Received GitHub event: {event.event_type}.{event.action}")

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
        """
        self._tick_count += 1

        event = GovernanceScanStarted(tick_count=self._tick_count)

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
