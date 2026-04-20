"""Manager dispatch-intent handler."""

import asyncio
from typing import Callable

from loguru import logger

from vibe3.domain.events import DomainEvent
from vibe3.domain.events.flow_lifecycle import ManagerDispatched
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.manager import build_manager_request


def handle_manager_dispatched(event: ManagerDispatched) -> None:
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
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role="manager",
                    issue_number=event.issue_number,
                    error="issue_not_found",
                ).error("Failed to fetch issue details from GitHub")
                return

            issue_info = IssueInfo.from_github_payload(issue_data)
            if issue_info is None:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role="manager",
                    issue_number=event.issue_number,
                    error="invalid_issue_data",
                ).error("Failed to parse issue data from GitHub response")
                return

            issue_info.state = target_state

        if issue_info is None:
            logger.bind(
                domain="issue_state_dispatch_handler",
                role="manager",
                issue_number=event.issue_number,
            ).error("Issue info is None, cannot dispatch role")
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
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role="manager",
                    issue_number=event.issue_number,
                ).error("Failed to prepare role execution request")
                
                # Fail the issue explicitly to avoid silent freeze
                from vibe3.services.issue_failure_service import fail_manager_issue
                
                await loop.run_in_executor(
                    None,
                    lambda: fail_manager_issue(
                        issue_number=event.issue_number,
                        reason=(
                            "Manager dispatch failed: build_manager_request returned None. "
                            "Possible causes: flow creation failed, capacity reached, or branch error. "
                            "Check orchestra logs for details."
                        ),
                        actor="orchestra:issue_state_dispatch",
                    ),
                )
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

    subscribe(
        "ManagerDispatched",
        cast(Callable[[DomainEvent], None], handle_manager_dispatched),
    )

    logger.bind(domain="events").info("Issue-state role dispatch handlers registered")
