"""Manager dispatch-intent handler."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.clients.store_context import get_store
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.domain.events.flow_lifecycle import ManagerDispatchIntent
from vibe3.domain.handler_registry import register_handler
from vibe3.exceptions import CapacityDeferredError
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.manager import build_manager_request
from vibe3.services.error_helpers import record_dispatch_failure_if_unexpected
from vibe3.services.issue_failure_service import block_manager_noop_issue

if TYPE_CHECKING:
    from vibe3.agents import CodeagentBackend
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.config.orchestra_settings import OrchestraConfig
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.execution.capacity_service import CapacityService
    from vibe3.execution.coordinator import ExecutionCoordinator


@dataclass
class DispatchContext:
    """Pre-configured services for manager dispatch."""

    config: "OrchestraConfig"
    backend: "CodeagentBackend"
    capacity: "CapacityService"
    github_client: "GitHubClient"
    registry: "SessionRegistryService"
    coordinator: "ExecutionCoordinator"


def build_dispatch_context(
    config: "OrchestraConfig",
    store: "SQLiteClient",
) -> DispatchContext:
    """Construct all dispatch services from base dependencies."""
    from vibe3.agents import CodeagentBackend
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.execution.capacity_service import CapacityService
    from vibe3.execution.coordinator import ExecutionCoordinator

    backend = CodeagentBackend()
    return DispatchContext(
        config=config,
        backend=backend,
        capacity=CapacityService(config, store, backend),
        github_client=_lazy_github_client(),
        registry=SessionRegistryService(store=store, backend=backend),
        coordinator=ExecutionCoordinator(config, store, backend=backend),
    )


def _lazy_github_client() -> "GitHubClient":
    from vibe3.clients.github_client import GitHubClient

    return GitHubClient()


@register_handler("ManagerDispatchIntent")
def handle_manager_dispatch_intent(
    event: ManagerDispatchIntent,
    /,
    dispatch_context: DispatchContext | None = None,
) -> None:
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

    async def _do_dispatch(ctx: DispatchContext) -> None:
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

        loop = asyncio.get_running_loop()

        # Early capacity check BEFORE expensive work (GitHub fetch, coordinator setup)
        # to avoid wasteful network/DB operations when system is at capacity
        if not ctx.capacity.can_dispatch("manager"):
            return  # CapacityService.can_dispatch already logs INFO

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
            issue_data = await loop.run_in_executor(
                None, lambda: ctx.github_client.view_issue(event.issue_number)
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

        try:
            request = await loop.run_in_executor(
                None,
                lambda: build_manager_request(
                    ctx.config,
                    issue_info,
                    registry=ctx.registry,
                    tick_id=event.tick_id,
                ),
            )

        except CapacityDeferredError as exc:
            # Capacity defer is normal — just log and return (don't block)
            logger.bind(
                domain="issue_state_dispatch_handler",
                role="manager",
                issue_number=event.issue_number,
            ).info(f"Manager dispatch deferred: {exc.message}")
            return

        if request is None:
            _block_for_noop("Failed to prepare role execution request")
            return

        try:
            result = await loop.run_in_executor(
                None, lambda: ctx.coordinator.dispatch_execution(request)
            )
            record_dispatch_failure_if_unexpected(
                result=result,
                role="manager",
                issue_number=event.issue_number,
                branch=event.branch,
                tick_id=event.tick_id,
                dispatch_source="automatic",
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
            record_dispatch_failure_if_unexpected(
                role="manager",
                issue_number=event.issue_number,
                branch=event.branch,
                exception=exc,
                tick_id=event.tick_id,
                dispatch_source="automatic",
            )
            logger.bind(
                domain="issue_state_dispatch_handler",
                role="manager",
                issue_number=event.issue_number,
            ).exception(f"Role dispatch failed: {exc}")

    try:
        loop = asyncio.get_running_loop()
        if dispatch_context is None:
            config = load_orchestra_config()
            with get_store() as store:
                dispatch_context = build_dispatch_context(config, store)
                loop.create_task(
                    _do_dispatch(dispatch_context),
                    name=f"manager-dispatch-{event.issue_number}-{event.trigger_state}",
                )
        else:
            loop.create_task(
                _do_dispatch(dispatch_context),
                name=f"manager-dispatch-{event.issue_number}-{event.trigger_state}",
            )
    except RuntimeError:
        # No event loop running, run synchronously
        if dispatch_context is None:
            config = load_orchestra_config()
            with get_store() as store:
                dispatch_context = build_dispatch_context(config, store)
        asyncio.run(_do_dispatch(dispatch_context))
