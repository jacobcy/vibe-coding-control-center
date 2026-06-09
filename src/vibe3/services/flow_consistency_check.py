"""Re-export shim — flow consistency moved to vibe3.services.flow.consistency."""

from vibe3.services.flow.consistency import (
    FlowConsistencyCode,
    FlowConsistencyResult,
    apply_consistency_fix,
    check_flow_consistency,
)

__all__ = [
    "FlowConsistencyCode",
    "FlowConsistencyResult",
    "apply_consistency_fix",
    "check_flow_consistency",
]
