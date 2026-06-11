"""Orchestra - GitHub heartbeat-driven orchestration shell.

Primary entry point: HeartbeatServer (vibe3 serve start)
  - OrchestrationFacade: unified service for governance, supervisor, and dispatch
  - Polling heartbeat every 15 min via on_tick()

Self-module re-exports for orchestra components.
Import from vibe3.orchestra for symbols defined within this module.
For cross-module symbols (domain, observability, services, models, clients),
import directly from their source modules.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.orchestra.domain_types import (
        CapacityServiceProtocol,
        CheckServiceProtocol,
        CleanupServiceProtocol,
        FlowManagerProtocol,
        FlowServiceProtocol,
        GateResult,
        GateStatus,
        IssueCollectionServiceProtocol,
        LabelDispatchCallable,
        LabelServiceProtocol,
        QualifyGateServiceProtocol,
        ServiceBase,
    )
    from vibe3.orchestra.issue_loader import (
        get_flow_context,
        get_flow_context_bulk,
        is_auto_task_branch,
        load_issue,
    )
    from vibe3.orchestra.queue_operations import (
        promote_progressed_entries,
        select_ready_issues_from_collected_issues,
    )
    from vibe3.orchestra.queue_persistence_service import QueuePersistenceService

_LAZY_IMPORTS: dict[str, str] = {
    # Orchestra submodules (self-module re-exports only)
    "create_global_dispatch_coordinator": (
        "vibe3.orchestra.dispatch_coordinator_factory"
    ),
    "select_ready_issues_from_collected_issues": "vibe3.orchestra.queue_operations",
    "promote_progressed_entries": "vibe3.orchestra.queue_operations",
    "QueuePersistenceService": "vibe3.orchestra.queue_persistence_service",
    "get_flow_context": "vibe3.orchestra.issue_loader",
    "get_flow_context_bulk": "vibe3.orchestra.issue_loader",
    "load_issue": "vibe3.orchestra.issue_loader",
    "is_auto_task_branch": "vibe3.orchestra.issue_loader",
    # Protocols (self-module re-exports only)
    "CheckServiceProtocol": "vibe3.orchestra.protocols",
    "FlowServiceProtocol": "vibe3.orchestra.protocols",
    "CapacityServiceProtocol": "vibe3.orchestra.protocols",
    "IssueCollectionServiceProtocol": "vibe3.orchestra.protocols",
    "FlowManagerProtocol": "vibe3.orchestra.protocols",
    "LabelDispatchCallable": "vibe3.orchestra.protocols",
    # Domain types (from orchestra.domain_types)
    "ServiceBase": "vibe3.orchestra.domain_types",
    "GateResult": "vibe3.orchestra.domain_types",
    "GateStatus": "vibe3.orchestra.domain_types",
    "CleanupServiceProtocol": "vibe3.orchestra.domain_types",
    "LabelServiceProtocol": "vibe3.orchestra.domain_types",
    "QualifyGateServiceProtocol": "vibe3.orchestra.domain_types",
}


def __getattr__(name: str) -> object:
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Orchestra submodules (self-module re-exports only)
    "create_global_dispatch_coordinator",
    "select_ready_issues_from_collected_issues",
    "promote_progressed_entries",
    "QueuePersistenceService",
    "get_flow_context",
    "get_flow_context_bulk",
    "load_issue",
    "is_auto_task_branch",
    # Protocols (self-module re-exports only)
    "CheckServiceProtocol",
    "FlowServiceProtocol",
    "CapacityServiceProtocol",
    "IssueCollectionServiceProtocol",
    "FlowManagerProtocol",
    "LabelDispatchCallable",
    # Domain types
    "ServiceBase",
    "GateResult",
    "GateStatus",
    "CleanupServiceProtocol",
    "LabelServiceProtocol",
    "QualifyGateServiceProtocol",
]
