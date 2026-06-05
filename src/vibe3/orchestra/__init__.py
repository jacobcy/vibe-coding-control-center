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

# Lazy imports via __getattr__ for everything else to avoid circular dependencies
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
    from vibe3.orchestra.queue_ordering import (
        resolve_priority,
        resolve_roadmap_rank,
        sort_ready_issues,
    )
    from vibe3.orchestra.queue_persistence_service import QueuePersistenceService
    from vibe3.services import (
        CheckResult,
        get_manager_usernames,
        should_skip_from_queue,
    )


def __getattr__(name: str) -> object:
    """Lazy import for all symbols to avoid circular dependencies.

    All symbols (orchestra submodules, domain, services) are imported lazily
    to prevent circular import issues.
    """
    # Orchestra submodule symbols
    if name == "QueueEntry":
        from vibe3.models import QueueEntry

        return QueueEntry
    if name == "FailedGate":
        from vibe3.domain.failed_gate import FailedGate

        return FailedGate
    if name == "append_governance_event":
        from vibe3.observability import append_governance_event

        return append_governance_event
    if name == "append_orchestra_event":
        from vibe3.observability import append_orchestra_event

        return append_orchestra_event
    if name == "append_orchestra_run_separator":
        from vibe3.observability import append_orchestra_run_separator

        return append_orchestra_run_separator
    if name == "orchestra_events_log_path":
        from vibe3.observability import orchestra_events_log_path

        return orchestra_events_log_path
    if name == "orchestra_log_dir":
        from vibe3.observability import orchestra_log_dir

        return orchestra_log_dir
    if name == "resolve_priority":
        from vibe3.orchestra.queue_ordering import resolve_priority

        return resolve_priority
    if name == "resolve_roadmap_rank":
        from vibe3.orchestra.queue_ordering import resolve_roadmap_rank

        return resolve_roadmap_rank
    if name == "sort_ready_issues":
        from vibe3.orchestra.queue_ordering import sort_ready_issues

        return sort_ready_issues
    if name == "select_ready_issues_from_collected_issues":
        from vibe3.orchestra.queue_operations import (
            select_ready_issues_from_collected_issues,
        )

        return select_ready_issues_from_collected_issues
    if name == "promote_progressed_entries":
        from vibe3.orchestra.queue_operations import promote_progressed_entries

        return promote_progressed_entries
    if name == "QueuePersistenceService":
        from vibe3.orchestra.queue_persistence_service import QueuePersistenceService

        return QueuePersistenceService
    if name == "DispatchHealthCheckService":
        from vibe3.orchestra.dispatch_health_check import DispatchHealthCheckService

        return DispatchHealthCheckService
    if name == "get_flow_context":
        from vibe3.orchestra.issue_loader import get_flow_context

        return get_flow_context
    if name == "load_issue":
        from vibe3.orchestra.issue_loader import load_issue

        return load_issue
    if name == "is_auto_task_branch":
        from vibe3.orchestra.issue_loader import is_auto_task_branch

        return is_auto_task_branch
    if name == "CheckServiceProtocol":
        from vibe3.orchestra.protocols import CheckServiceProtocol

        return CheckServiceProtocol
    if name == "FlowServiceProtocol":
        from vibe3.orchestra.protocols import FlowServiceProtocol

        return FlowServiceProtocol
    if name == "CapacityServiceProtocol":
        from vibe3.orchestra.protocols import CapacityServiceProtocol

        return CapacityServiceProtocol
    if name == "IssueCollectionServiceProtocol":
        from vibe3.orchestra.protocols import IssueCollectionServiceProtocol

        return IssueCollectionServiceProtocol
    if name == "FlowManagerProtocol":
        from vibe3.orchestra.protocols import FlowManagerProtocol

        return FlowManagerProtocol
    if name == "LabelDispatchCallable":
        from vibe3.orchestra.protocols import LabelDispatchCallable

        return LabelDispatchCallable

    # Domain symbols (domain/ imports from orchestra submodules)
    if name == "MAX_INTENTS_PER_TICK":
        from vibe3.domain.dispatch_coordinator import MAX_INTENTS_PER_TICK

        return MAX_INTENTS_PER_TICK
    if name == "QualifyGateService":
        from vibe3.domain.qualify_gate import QualifyGateService

        return QualifyGateService
    if name == "find_role_for_state":
        from vibe3.domain.role_resolver import find_role_for_state

        return find_role_for_state
    if name == "GateResult":
        from vibe3.domain.failed_gate import GateResult

        return GateResult
    if name == "GateStatus":
        from vibe3.domain.failed_gate import GateStatus

        return GateStatus

    # Services symbols (services/ may import from orchestra)
    if name == "CheckResult":
        from vibe3.services import CheckResult

        return CheckResult
    if name == "should_skip_from_queue":
        from vibe3.services import should_skip_from_queue

        return should_skip_from_queue
    if name == "get_manager_usernames":
        from vibe3.services import get_manager_usernames

        return get_manager_usernames

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
