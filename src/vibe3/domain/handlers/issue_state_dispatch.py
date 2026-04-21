"""Manager dispatch-intent handler."""

import asyncio
from typing import Callable

from loguru import logger

from vibe3.domain.events import DomainEvent
from vibe3.domain.events.flow_lifecycle import ManagerDispatchIntent
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.manager import build_manager_request
from vibe3.services.issue_failure_service import block_manager_noop_issue


def handle_manager_dispatch_intent(event: ManagerDispatchIntent) -> None:
    """Dispatch manager from an authoritative dispatch-intent event."""
    if event.actor == "human:resume":
        logger.bind(
            domain="issue_state_dispatch_handler",
            issue_number=event.issue_number,
            trigger_state=event.trigger_state,
            actor=event.actor,
        ).info("Skipping auto-dispatch for human resume event")
        return

    if event.trigger_state not in {
        IssueState.READY.value,
        IssueState.HANDOFF.value,
    }:
        return

    logger.bind(
        domain="issue_state_dispatch_handler",
        role="manager",
        issue_number=event.issue_number,
        trigger_state=event.trigger_state,
        branch=event.branch,
    ).info("Manager dispatch intent received, scheduling async dispatch")

    async def _do_dispatch() -> None:
        def _block_for_noop(reason: str) -> None:
            logger.bind(
                domain="issue_state_dispatch_handler",
                role="manager",
                issue_number=event.issue_number,
            ).error(reason)
            block_manager_noop_issue(
                issue_number=event.issue_number,
                repo=None,
                reason=reason,
                actor="agent:manager",
            )

        loop = asyncio.get_event_loop()
        config = OrchestraConfig.from_settings()

        target_state = (
            IssueState.READY
            if event.trigger_state == IssueState.READY.value
            else IssueState.HANDOFF
        )

        if event.issue_title is not None:
            issue_info: IssueInfo | None = IssueInfo(
                number=event.issue_number,
                title=event.issue_title,
                state=target_state,
            )
        else:
            from vibe3.clients.github_client import GitHubClient

            github_client = GitHubClient()
            issue_data = await loop.run_in_executor(
                None, lambda: github_client.view_issue(event.issue_number)
            )

            if issue_data is None or isinstance(issue_data, str):
                _block_for_noop(
                    "Failed to fetch issue details from GitHub for manager dispatch"
                )
                return

            issue_info = IssueInfo.from_github_payload(issue_data)
            if issue_info is None:
                _block_for_noop(
                    "Failed to parse issue data from GitHub"
                    " response for manager dispatch"
                )
                return

            issue_info.state = target_state

        if issue_info is None:
            _block_for_noop("Issue info is None, cannot dispatch manager role")
            return

        from vibe3.agents.backends.codeagent import CodeagentBackend
        from vibe3.clients.sqlite_client import SQLiteClient
        from vibe3.environment.session_registry import SessionRegistryService
        from vibe3.execution.coordinator import ExecutionCoordinator

        store = SQLiteClient()
        backend = CodeagentBackend()
        registry = SessionRegistryService(store=store, backend=backend)
        coordinator = ExecutionCoordinator(config, store)

        try:
            request = await loop.run_in_executor(
                None,
                lambda: build_manager_request(
                    config,
                    issue_info,
                    registry=registry,
                ),
            )

            if request is None:
                _block_for_noop("Failed to prepare role execution request")
                return

            result = await loop.run_in_executor(
                None, lambda: coordinator.dispatch_execution(request)
            )

            if result.launched:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role="manager",
                    issue_number=event.issue_number,
                ).success("Role execution launched via ExecutionCoordinator")
            elif result.skipped:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role="manager",
                    issue_number=event.issue_number,
                ).info(f"Role dispatch skipped: {result.reason}")
            else:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role="manager",
                    issue_number=event.issue_number,
                ).warning(f"Role dispatch failed: {result.reason}")

        except Exception as exc:
            logger.bind(
                domain="issue_state_dispatch_handler",
                role="manager",
                issue_number=event.issue_number,
            ).exception(f"Role dispatch failed: {exc}")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            _do_dispatch(),
            name=f"manager-dispatch-{event.issue_number}-{event.trigger_state}",
        )
    except RuntimeError:
        asyncio.run(_do_dispatch())


def register_issue_state_dispatch_handlers() -> None:
    """Register manager dispatch-intent handlers."""
    from typing import cast

    from vibe3.domain.publisher import subscribe

    # Subscribe to new event name
    subscribe(
        "ManagerDispatchIntent",
        cast(Callable[[DomainEvent], None], handle_manager_dispatch_intent),
    )
    # Backward compatibility: subscribe to old event name
    subscribe(
        "ManagerDispatched",
        cast(Callable[[DomainEvent], None], handle_manager_dispatch_intent),
    )

    logger.bind(domain="events").info("Issue-state role dispatch handlers registered")
