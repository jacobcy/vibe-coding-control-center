"""Re-export shim for FlowOrchestratorService.

The actual implementation has moved to
vibe3.services.orchestra.orchestrator.
"""

from vibe3.services.orchestra.orchestrator import FlowOrchestratorService

__all__ = ["FlowOrchestratorService"]
