"""Flow domain services subpackage.

Public API Contract:
- FlowService: Main flow orchestration service
- FlowCategory, FlowState, classify_flow, get_flow_state: Flow classification
- BlockedStateService, BlockedState, BlockedStateIO: Blocked state management
- FlowCleanupService, FlowRecoveryService: Cleanup and recovery
- FlowProjection, FlowProjectionService: Flow projections
- FlowRebuildUsecase, FlowStatusService, FlowStatusResolver: Core utilities
- create_flow_manager, infer_resume_label: Factory and utilities

All other symbols are internal to the flow package and should be imported directly.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.flow.abandon import AbandonFlowService
    from vibe3.services.flow.blocked_state_io import (
        BlockedStateIO,
    )
    from vibe3.services.flow.blocked_state_service import BlockedStateService
    from vibe3.services.flow.blocked_state_types import (
        BlockedState,
        ConsistencyReport,
        UnblockResult,
    )
    from vibe3.services.flow.branch_resolution import (
        resolve_branch_and_issue,
        resolve_branch_arg,
    )
    from vibe3.services.flow.classifier import (
        FlowCategory,
        FlowState,
        classify_flow,
        get_flow_state,
    )
    from vibe3.services.flow.cleanup import (
        FlowCleanupService,
        LiveSessionsDetectedError,
    )
    from vibe3.services.flow.event_projection import build_event_projection_hook
    from vibe3.services.flow.factory import create_flow_manager
    from vibe3.services.flow.projection import FlowProjection, FlowProjectionService
    from vibe3.services.flow.rebuild import FlowRebuildUsecase
    from vibe3.services.flow.recovery import FlowRecoveryService
    from vibe3.services.flow.resume_resolver import infer_resume_label
    from vibe3.services.flow.service import FlowService, resolve_flow_ref
    from vibe3.services.flow.status import FlowStatusService
    from vibe3.services.flow.status_resolver import FlowStatusResolver
    from vibe3.services.flow.timeline import FlowTimelineService

__all__ = [
    "AbandonFlowService",
    "BlockedState",
    "BlockedStateIO",
    "BlockedStateService",
    "ConsistencyReport",
    "UnblockResult",
    "FlowCategory",
    "FlowState",
    "classify_flow",
    "get_flow_state",
    "FlowCleanupService",
    "LiveSessionsDetectedError",
    "build_event_projection_hook",
    "create_flow_manager",
    "FlowProjection",
    "FlowProjectionService",
    "FlowRebuildUsecase",
    "FlowRecoveryService",
    "infer_resume_label",
    "resolve_branch_and_issue",
    "resolve_branch_arg",
    "FlowService",
    "resolve_flow_ref",
    "FlowStatusResolver",
    "FlowStatusService",
    "FlowTimelineService",
]

_SYMBOL_MODULES = {
    "AbandonFlowService": "vibe3.services.flow.abandon",
    "BlockedState": "vibe3.services.flow.blocked_state_types",
    "BlockedStateIO": "vibe3.services.flow.blocked_state_io",
    "BlockedStateService": "vibe3.services.flow.blocked_state_service",
    "ConsistencyReport": "vibe3.services.flow.blocked_state_types",
    "UnblockResult": "vibe3.services.flow.blocked_state_types",
    "FlowCategory": "vibe3.services.flow.classifier",
    "FlowState": "vibe3.services.flow.classifier",
    "classify_flow": "vibe3.services.flow.classifier",
    "get_flow_state": "vibe3.services.flow.classifier",
    "FlowCleanupService": "vibe3.services.flow.cleanup",
    "LiveSessionsDetectedError": "vibe3.services.flow.cleanup",
    "build_event_projection_hook": "vibe3.services.flow.event_projection",
    "create_flow_manager": "vibe3.services.flow.factory",
    "FlowProjection": "vibe3.services.flow.projection",
    "FlowProjectionService": "vibe3.services.flow.projection",
    "FlowRebuildUsecase": "vibe3.services.flow.rebuild",
    "FlowRecoveryService": "vibe3.services.flow.recovery",
    "infer_resume_label": "vibe3.services.flow.resume_resolver",
    "resolve_branch_and_issue": "vibe3.services.flow.branch_resolution",
    "resolve_branch_arg": "vibe3.services.flow.branch_resolution",
    "FlowService": "vibe3.services.flow.service",
    "resolve_flow_ref": "vibe3.services.flow.service",
    "FlowStatusResolver": "vibe3.services.flow.status_resolver",
    "FlowStatusService": "vibe3.services.flow.status",
    "FlowTimelineService": "vibe3.services.flow.timeline",
}


def __getattr__(name: str) -> Any:
    """Lazy import for Flow services symbols to avoid circular dependencies.

    This allows external modules to use:
        from vibe3.services.flow import FlowService, FlowRebuildUsecase

    While avoiding circular imports at module load time.
    """
    if name in _SYMBOL_MODULES:
        import importlib

        module = importlib.import_module(_SYMBOL_MODULES[name])
        symbol = getattr(module, name)
        # Cache in module globals for faster subsequent access
        globals()[name] = symbol
        return symbol

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
