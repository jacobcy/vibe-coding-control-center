"""Re-export shim for actor support functions.

The actual implementation has moved to
vibe3.services.shared.actors.
"""

from vibe3.services.shared.actors import (
    extract_role_from_actor,
    format_agent_actor,
    resolve_actor_backend_model,
)

__all__ = [
    "resolve_actor_backend_model",
    "format_agent_actor",
    "extract_role_from_actor",
]
