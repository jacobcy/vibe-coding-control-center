"""Orchestra - GitHub heartbeat-driven orchestration shell.

Primary entry point: HeartbeatServer (vibe3 serve start)
  - OrchestrationFacade: unified service for governance, supervisor, and dispatch
  - Polling heartbeat every 15 min via on_tick()

This module serves as the unified public interface for orchestra components.
Import from vibe3.orchestra instead of submodules to ensure clean dependencies.
"""

from typing import TYPE_CHECKING

# Module-level re-exports from clients/ (safe, no cycle risk)
from vibe3.clients import GitClient

# Module-level re-exports from models/ (safe, no cycle risk)
from vibe3.models import OrchestraConfig

if TYPE_CHECKING:
    from vibe3.domain.dispatch_coordinator import MAX_INTENTS_PER_TICK
    from vibe3.domain.failed_gate import FailedGate, GateResult, GateStatus
    from vibe3.domain.qualify_gate import QualifyGateService
    from vibe3.domain.role_resolver import find_role_for_state
    from vibe3.models import QueueEntry
    from vibe3.observability import (
        append_governance_event,
        append_orchestra_event,
        append_orchestra_run_separator,
        orchestra_events_log_path,
        orchestra_log_dir,
    )
    from vibe3.orchestra.dispatch_health_check import DispatchHealthCheckService
    from vibe3.orchestra.issue_loader import (
        get_flow_context,
        is_auto_task_branch,
        load_issue,
    )
    from vibe3.orchestra.protocols import (
        CapacityServiceProtocol,
        CheckServiceProtocol,
        FlowManagerProtocol,
        FlowServiceProtocol,
        IssueCollectionServiceProtocol,
        LabelDispatchCallable,
    )
    from vibe3.orchestra.queue_operations import (
        promote_progressed_entries,
        select_ready_issues_from_collected_issues,
    )
    from vibe3.orchestra.queue_persistence_service import QueuePersistenceService
    from vibe3.services import (
        CheckResult,
        get_manager_usernames,
        should_skip_from_queue,
    )
    from vibe3.utils.queue_ordering import (
        resolve_priority,
        resolve_roadmap_rank,
        sort_ready_issues,
    )

_LAZY_IMPORTS: dict[str, str] = {
    # Models
    "QueueEntry": "vibe3.models",
    # Domain
    "FailedGate": "vibe3.domain.failed_gate",
    "GateResult": "vibe3.domain.failed_gate",
    "GateStatus": "vibe3.domain.failed_gate",
    "MAX_INTENTS_PER_TICK": "vibe3.domain.dispatch_coordinator",
    "QualifyGateService": "vibe3.domain.qualify_gate",
    "find_role_for_state": "vibe3.domain.role_resolver",
    # Observability
    "append_governance_event": "vibe3.observability",
    "append_orchestra_event": "vibe3.observability",
    "append_orchestra_run_separator": "vibe3.observability",
    "orchestra_events_log_path": "vibe3.observability",
    "orchestra_log_dir": "vibe3.observability",
    # Utils
    "resolve_priority": "vibe3.utils.queue_ordering",
    "resolve_roadmap_rank": "vibe3.utils.queue_ordering",
    "sort_ready_issues": "vibe3.utils.queue_ordering",
    # Orchestra submodules
    "create_global_dispatch_coordinator": "vibe3.orchestra.dispatch_coordinator_factory",  # noqa: E501
    "select_ready_issues_from_collected_issues": "vibe3.orchestra.queue_operations",
    "promote_progressed_entries": "vibe3.orchestra.queue_operations",
    "QueuePersistenceService": "vibe3.orchestra.queue_persistence_service",
    "DispatchHealthCheckService": "vibe3.orchestra.dispatch_health_check",
    "get_flow_context": "vibe3.orchestra.issue_loader",
    "load_issue": "vibe3.orchestra.issue_loader",
    "is_auto_task_branch": "vibe3.orchestra.issue_loader",
    # Protocols
    "CheckServiceProtocol": "vibe3.orchestra.protocols",
    "FlowServiceProtocol": "vibe3.orchestra.protocols",
    "CapacityServiceProtocol": "vibe3.orchestra.protocols",
    "IssueCollectionServiceProtocol": "vibe3.orchestra.protocols",
    "FlowManagerProtocol": "vibe3.orchestra.protocols",
    "LabelDispatchCallable": "vibe3.orchestra.protocols",
    # Services
    "CheckResult": "vibe3.services",
    "should_skip_from_queue": "vibe3.services",
    "get_manager_usernames": "vibe3.services",
}


def __getattr__(name: str) -> object:
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Models
    "OrchestraConfig",
    # Orchestra submodules
    "QueueEntry",
    "FailedGate",
    "append_governance_event",
    "append_orchestra_event",
    "append_orchestra_run_separator",
    "orchestra_events_log_path",
    "orchestra_log_dir",
    "resolve_priority",
    "resolve_roadmap_rank",
    "sort_ready_issues",
    "select_ready_issues_from_collected_issues",
    "promote_progressed_entries",
    "QueuePersistenceService",
    "DispatchHealthCheckService",
    "create_global_dispatch_coordinator",
    "get_flow_context",
    "load_issue",
    "is_auto_task_branch",
    # Protocols
    "CheckServiceProtocol",
    "FlowServiceProtocol",
    "CapacityServiceProtocol",
    "IssueCollectionServiceProtocol",
    "FlowManagerProtocol",
    "LabelDispatchCallable",
    # Clients
    "GitClient",
    # Domain (via __getattr__)
    "MAX_INTENTS_PER_TICK",
    "QualifyGateService",
    "find_role_for_state",
    "GateResult",
    "GateStatus",
    # Services (via __getattr__)
    "CheckResult",
    "should_skip_from_queue",
    "get_manager_usernames",
]
