"""Runtime factory for wiring the dispatch coordinator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vibe3.domain.dispatch_coordinator import GlobalDispatchCoordinator
from vibe3.orchestra.dispatch_health_check import DispatchHealthCheckService
from vibe3.orchestra.issue_loader import get_flow_context, load_issue
from vibe3.orchestra.queue_operations import select_ready_issues_from_collected_issues
from vibe3.orchestra.queue_persistence_service import QueuePersistenceService
from vibe3.services.check_service import CheckService
from vibe3.services.flow_service import FlowService

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.domain.protocols.flow_protocols import FlowManagerProtocol
    from vibe3.environment.session_registry import SessionRegistryService
    from vibe3.execution.capacity_service import CapacityService
    from vibe3.models import IssueInfo
    from vibe3.models.orchestra_config import OrchestraConfig


def create_global_dispatch_coordinator(
    *,
    config: "OrchestraConfig",
    capacity: "CapacityService",
    github: "GitHubClient",
    store: "SQLiteClient",
    flow_manager: "FlowManagerProtocol",
    registry: "SessionRegistryService | None",
) -> GlobalDispatchCoordinator:
    """Create GlobalDispatchCoordinator with orchestra runtime services."""
    check_service = CheckService(
        store=store,
        git_client=flow_manager.git,
        github_client=github,
    )
    flow_blocker = FlowService(
        store=store,
        git_client=flow_manager.git,
    )

    def flow_context_resolver(
        issue_number: int,
    ) -> tuple[str, dict[str, object] | None]:
        return get_flow_context(issue_number, config, github, store, flow_manager)

    def issue_loader(issue_number: int) -> "IssueInfo | None":
        return load_issue(issue_number, config, github)

    health_check_service = DispatchHealthCheckService(
        check_service=check_service,
        flow_blocker=flow_blocker,
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
    )

    return GlobalDispatchCoordinator(
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
    )
