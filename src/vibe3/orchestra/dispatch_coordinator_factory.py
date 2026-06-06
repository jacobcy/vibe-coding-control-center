"""Runtime factory for wiring the dispatch coordinator."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from vibe3.orchestra import (
    DispatchHealthCheckService,
    QueuePersistenceService,
    get_flow_context,
    load_issue,
    select_ready_issues_from_collected_issues,
)

if TYPE_CHECKING:
    from vibe3.clients import GitHubClient, SQLiteClient
    from vibe3.domain.events.coalescing import DispatchCoalescer
    from vibe3.environment import SessionRegistryService
    from vibe3.execution import CapacityService
    from vibe3.models import IssueInfo, OrchestraConfig
    from vibe3.orchestra import FlowManagerProtocol
    from vibe3.orchestra.domain_types import (
        CheckServiceProtocol,
        FlowServiceProtocol,
    )


def create_global_dispatch_coordinator(
    *,
    config: "OrchestraConfig",
    capacity: "CapacityService",
    github: "GitHubClient",
    store: "SQLiteClient",
    flow_manager: "FlowManagerProtocol",
    registry: "SessionRegistryService | None",
    coordinator_class: type,
    check_service: "CheckServiceProtocol",
    flow_service: "FlowServiceProtocol",
    queue_filter: Callable[..., bool] | None = None,
    coalescer: "DispatchCoalescer | None" = None,
) -> object:
    """Create GlobalDispatchCoordinator with orchestra runtime services."""

    def flow_context_resolver(
        issue_number: int,
    ) -> tuple[str, dict[str, object] | None]:
        return get_flow_context(issue_number, config, github, store, flow_manager)

    def issue_loader(issue_number: int) -> "IssueInfo | None":
        return load_issue(issue_number, config, github)

    health_check_service = DispatchHealthCheckService(
        check_service=check_service,
        flow_blocker=flow_service,
        store=store,
        flow_context_resolver=flow_context_resolver,
    )
    queue_persistence = QueuePersistenceService(
        store=store,
        config=config,
        github=github,
        registry=registry,
        supervisor_label=config.supervisor_handoff.issue_label,
        load_issue=issue_loader,
        queue_filter=queue_filter,
    )

    return coordinator_class(
        config=config,
        capacity=capacity,
        github=github,
        store=store,
        flow_manager=flow_manager,
        registry=registry,
        health_check_service=health_check_service,
        queue_persistence=queue_persistence,
        issue_loader=issue_loader,
        flow_context_resolver=flow_context_resolver,
        queue_selector=select_ready_issues_from_collected_issues,
        check_service=check_service,
        coalescer=coalescer,
    )
