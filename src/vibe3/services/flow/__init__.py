"""Flow domain services subpackage."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.services.flow.block_mixin import FlowLifecycleMixin
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
    from vibe3.services.flow.consistency import (
        FlowConsistencyCode,
        FlowConsistencyResult,
        apply_consistency_fix,
        check_flow_consistency,
    )
    from vibe3.services.flow.factory import create_flow_manager
    from vibe3.services.flow.projection import FlowProjection, FlowProjectionService
    from vibe3.services.flow.read_mixin import FlowReadMixin
    from vibe3.services.flow.reader import FlowReader
    from vibe3.services.flow.rebuild import FlowRebuildUsecase
    from vibe3.services.flow.rebuild_postconditions import assert_rebuild_postconditions
    from vibe3.services.flow.recovery import (
        FlowRecoveryService,
        RecoveryAction,
        RecoveryResult,
    )
    from vibe3.services.flow.resume_resolver import infer_resume_label
    from vibe3.services.flow.service import FlowService
    from vibe3.services.flow.status import FlowStatusService
    from vibe3.services.flow.status_resolver import FlowStatusResolver
    from vibe3.services.flow.timeline import TIMELINE_DISPLAY_MAP, FlowTimelineService
    from vibe3.services.flow.transition import FlowTransitionMixin
    from vibe3.services.flow.write_mixin import FlowWriteMixin

__all__ = [
    # Public API (exported via services/__init__.py)
    "FlowCategory",
    "FlowState",
    "classify_flow",
    "get_flow_state",
    "FlowCleanupService",
    "LiveSessionsDetectedError",
    "create_flow_manager",
    "FlowProjection",
    "FlowProjectionService",
    "FlowRebuildUsecase",
    "FlowRecoveryService",
    "infer_resume_label",
    "FlowService",
    "FlowStatusResolver",
    "FlowStatusService",
    # Internal API (used within flow package)
    "FlowConsistencyCode",
    "FlowConsistencyResult",
    "check_flow_consistency",
    "apply_consistency_fix",
    "FlowReadMixin",
    "FlowWriteMixin",
    "FlowLifecycleMixin",
    "FlowTransitionMixin",
    "assert_rebuild_postconditions",
    "RecoveryAction",
    "RecoveryResult",
    "FlowReader",
    "FlowTimelineService",
    "TIMELINE_DISPLAY_MAP",
]

_SYMBOL_MODULES = {
    # Public API
    "FlowCategory": "vibe3.services.flow.classifier",
    "FlowState": "vibe3.services.flow.classifier",
    "classify_flow": "vibe3.services.flow.classifier",
    "get_flow_state": "vibe3.services.flow.classifier",
    "FlowCleanupService": "vibe3.services.flow.cleanup",
    "LiveSessionsDetectedError": "vibe3.services.flow.cleanup",
    "create_flow_manager": "vibe3.services.flow.factory",
    "FlowProjection": "vibe3.services.flow.projection",
    "FlowProjectionService": "vibe3.services.flow.projection",
    "FlowRebuildUsecase": "vibe3.services.flow.rebuild",
    "FlowRecoveryService": "vibe3.services.flow.recovery",
    "infer_resume_label": "vibe3.services.flow.resume_resolver",
    "FlowService": "vibe3.services.flow.service",
    "FlowStatusResolver": "vibe3.services.flow.status_resolver",
    "FlowStatusService": "vibe3.services.flow.status",
    # Internal API
    "FlowConsistencyCode": "vibe3.services.flow.consistency",
    "FlowConsistencyResult": "vibe3.services.flow.consistency",
    "check_flow_consistency": "vibe3.services.flow.consistency",
    "apply_consistency_fix": "vibe3.services.flow.consistency",
    "FlowReadMixin": "vibe3.services.flow.read_mixin",
    "FlowWriteMixin": "vibe3.services.flow.write_mixin",
    "FlowLifecycleMixin": "vibe3.services.flow.block_mixin",
    "FlowTransitionMixin": "vibe3.services.flow.transition",
    "assert_rebuild_postconditions": "vibe3.services.flow.rebuild_postconditions",
    "RecoveryAction": "vibe3.services.flow.recovery",
    "RecoveryResult": "vibe3.services.flow.recovery",
    "FlowReader": "vibe3.services.flow.reader",
    "FlowTimelineService": "vibe3.services.flow.timeline",
    "TIMELINE_DISPLAY_MAP": "vibe3.services.flow.timeline",
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
