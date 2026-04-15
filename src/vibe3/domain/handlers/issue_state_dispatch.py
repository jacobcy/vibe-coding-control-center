"""Generic IssueStateChanged -> role dispatch handler."""

import asyncio
from typing import Callable

from loguru import logger

from vibe3.domain.events import DomainEvent
from vibe3.domain.events.flow_lifecycle import IssueStateChanged
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.registry import build_issue_state_request, resolve_issue_state_role


def handle_issue_state_changed_for_roles(event: IssueStateChanged) -> None:
    """Dispatch triggerable roles for IssueStateChanged events.

    Current supported issue-state role:
    - manager (ready / handoff)
    """
    if event.actor == "human:resume":
        logger.bind(
            domain="issue_state_dispatch_handler",
            issue_number=event.issue_number,
            to_state=event.to_state,
            actor=event.actor,
        ).info("Skipping auto-dispatch for human resume event")
        return

    role = resolve_issue_state_role(event.to_state)
    if role is None:
        return

    logger.bind(
        domain="issue_state_dispatch_handler",
        role=role.registry_role,
        issue_number=event.issue_number,
        from_state=event.from_state,
        to_state=event.to_state,
    ).info("Issue-state role handler triggered, scheduling async dispatch")

    async def _do_dispatch() -> None:
        loop = asyncio.get_event_loop()
        config = OrchestraConfig.from_settings()

        target_state = (
            IssueState.READY
            if event.to_state == IssueState.READY.value
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
                    role=role.registry_role,
                    issue_number=event.issue_number,
                    error="issue_not_found",
                ).error("Failed to fetch issue details from GitHub")
                return

            issue_info = IssueInfo.from_github_payload(issue_data)
            if issue_info is None:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role=role.registry_role,
                    issue_number=event.issue_number,
                    error="invalid_issue_data",
                ).error("Failed to parse issue data from GitHub response")
                return

            issue_info.state = target_state

        if issue_info is None:
            logger.bind(
                domain="issue_state_dispatch_handler",
                role=role.registry_role,
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
                lambda: build_issue_state_request(
                    config,
                    issue_info,
                    event.to_state,
                    registry=registry,
                ),
            )

            if request is None:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role=role.registry_role,
                    issue_number=event.issue_number,
                ).error("Failed to prepare role execution request")
                return

            result = await loop.run_in_executor(
                None, lambda: coordinator.dispatch_execution(request)
            )

            if result.launched:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role=role.registry_role,
                    issue_number=event.issue_number,
                ).success("Role execution launched via ExecutionCoordinator")
            elif result.skipped:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role=role.registry_role,
                    issue_number=event.issue_number,
                ).info(f"Role dispatch skipped: {result.reason}")
            else:
                logger.bind(
                    domain="issue_state_dispatch_handler",
                    role=role.registry_role,
                    issue_number=event.issue_number,
                ).warning(f"Role dispatch failed: {result.reason}")

        except Exception as exc:
            logger.bind(
                domain="issue_state_dispatch_handler",
                role=role.registry_role,
                issue_number=event.issue_number,
            ).exception(f"Role dispatch failed: {exc}")

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(
            _do_dispatch(),
            name=f"issue-state-role-dispatch-{event.issue_number}-{event.to_state}",
        )
    except RuntimeError:
        asyncio.run(_do_dispatch())


def register_issue_state_dispatch_handlers() -> None:
    """Register generic IssueStateChanged role dispatch handlers."""
    from typing import cast

    from vibe3.domain.publisher import subscribe

    subscribe(
        "IssueStateChanged",
        cast(Callable[[DomainEvent], None], handle_issue_state_changed_for_roles),
    )

    logger.bind(domain="events").info("Issue-state role dispatch handlers registered")
