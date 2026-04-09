"""Event handlers for manager dispatch."""

import asyncio
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from vibe3.domain.events import DomainEvent
from vibe3.domain.events.flow_lifecycle import IssueStateChanged
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState

_MANAGER_TRIGGER_STATES: frozenset[str] = frozenset({"ready", "handoff"})


def _resolve_repo_root() -> Path:
    """Resolve main repo root (git common-dir parent), same as server/registry.py."""
    try:
        from vibe3.clients.git_client import GitClient

        git_common_dir = GitClient().get_git_common_dir()
        if git_common_dir:
            return Path(git_common_dir).parent
    except Exception:
        pass
    return Path.cwd()


def _build_manager_adapter(config: OrchestraConfig) -> Any:
    """Build a ManagerRoleAdapter for manager-specific requirements.

    The adapter handles flow/worktree/command preparation,
    while ExecutionCoordinator handles capacity/lifecycle/launch.
    """
    from vibe3.agents.backends.codeagent import CodeagentBackend
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.execution.role_adapters import ManagerRoleAdapter

    store = SQLiteClient()
    backend = CodeagentBackend()
    registry = SessionRegistryService(store=store, backend=backend)
    return ManagerRoleAdapter(
        config,
        registry=registry,
        repo_path=_resolve_repo_root(),
    )


def handle_issue_state_changed_for_manager(event: IssueStateChanged) -> None:
    """Dispatch manager when an issue enters a manager-consumable state.

    Schedules the actual dispatch as an async task on the running event loop
    to avoid blocking the loop with synchronous I/O (same pattern as
    handle_governance_scan_started).

    Uses issue_title carried in the event payload (populated by OrchestrationFacade
    from the polling IssueInfo) to avoid a redundant view_issue GitHub API call.
    Falls back to fetching from GitHub only when the title is absent (webhook path).
    """
    if event.to_state not in _MANAGER_TRIGGER_STATES:
        return

    logger.bind(
        domain="manager_handler",
        issue_number=event.issue_number,
        from_state=event.from_state,
        to_state=event.to_state,
    ).info("Manager handler triggered, scheduling async dispatch")

    async def _do_dispatch() -> None:
        loop = asyncio.get_event_loop()
        config = OrchestraConfig.from_settings()

        target_state = (
            IssueState.READY if event.to_state == "ready" else IssueState.HANDOFF
        )

        if event.issue_title is not None:
            # Fast path: polling events carry the title → no GitHub API call needed.
            issue_info: IssueInfo | None = IssueInfo(
                number=event.issue_number,
                title=event.issue_title,
                state=target_state,
            )
        else:
            # Slow path: webhook events don't carry the title → fetch from GitHub.
            from vibe3.clients.github_client import GitHubClient

            github_client = GitHubClient()
            issue_data = await loop.run_in_executor(
                None, lambda: github_client.view_issue(event.issue_number)
            )

            if issue_data is None or isinstance(issue_data, str):
                logger.bind(
                    domain="manager_handler",
                    issue_number=event.issue_number,
                    error="issue_not_found",
                ).error("Failed to fetch issue details from GitHub")
                return

            issue_info = IssueInfo.from_github_payload(issue_data)
            if issue_info is None:
                logger.bind(
                    domain="manager_handler",
                    issue_number=event.issue_number,
                    error="invalid_issue_data",
                ).error("Failed to parse issue data from GitHub response")
                return

            issue_info.state = target_state

        if issue_info is None:
            logger.bind(
                domain="manager_handler",
                issue_number=event.issue_number,
            ).error("Issue info is None, cannot dispatch manager")
            return

        # Use unified ExecutionCoordinator path
        from vibe3.clients.sqlite_client import SQLiteClient
        from vibe3.execution.coordinator import ExecutionCoordinator

        manager_adapter = _build_manager_adapter(config)
        store = SQLiteClient()
        coordinator = ExecutionCoordinator(config, store)

        try:
            # Prepare manager-specific request
            request = await loop.run_in_executor(
                None, lambda: manager_adapter.prepare_execution_request(issue_info)
            )

            if request is None:
                logger.bind(
                    domain="manager_handler",
                    issue_number=event.issue_number,
                ).error("Failed to prepare manager execution request")
                return

            # Dispatch via unified coordinator
            result = await loop.run_in_executor(
                None, lambda: coordinator.dispatch_execution(request)
            )

            if result.launched:
                logger.bind(
                    domain="manager_handler",
                    issue_number=event.issue_number,
                ).success("Manager execution launched via ExecutionCoordinator")
            else:
                logger.bind(
                    domain="manager_handler",
                    issue_number=event.issue_number,
                ).warning(f"Manager dispatch failed: {result.reason}")

        except Exception as exc:
            logger.bind(
                domain="manager_handler",
                issue_number=event.issue_number,
            ).exception(f"Manager dispatch failed: {exc}")

    try:
        # Called from within heartbeat's async event loop — schedule as task.
        loop = asyncio.get_running_loop()
        loop.create_task(
            _do_dispatch(),
            name=f"manager-dispatch-{event.issue_number}-{event.to_state}",
        )
    except RuntimeError:
        # No running loop (e.g. tests, direct CLI call) — safe to use asyncio.run().
        asyncio.run(_do_dispatch())


def register_manager_handlers() -> None:
    """Register all manager event handlers."""
    from typing import cast

    from vibe3.domain.publisher import subscribe

    # Subscribe to IssueStateChanged for manager trigger
    subscribe(
        "IssueStateChanged",
        cast(Callable[[DomainEvent], None], handle_issue_state_changed_for_manager),
    )

    logger.bind(domain="events").info("Manager event handlers registered")
