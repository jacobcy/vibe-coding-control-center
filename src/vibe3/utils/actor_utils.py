"""Actor normalization utilities for display and PR body rendering.

This module re-exports normalize_actor from vibe3.models.actor_utils
to maintain backward compatibility while ensuring a single source of truth.

The canonical implementation lives in vibe3.models.actor_utils (models layer),
and this module provides a convenient import path for other layers.
"""

# Re-export from canonical location in models layer
from vibe3.models import (
    ACTOR_ALIAS_MAP,
    DISPLAY_PLACEHOLDER_ACTORS,
    PLACEHOLDER_ACTORS,
    normalize_actor,
)

__all__ = [
    "normalize_actor",
    "PLACEHOLDER_ACTORS",
    "DISPLAY_PLACEHOLDER_ACTORS",
    "ACTOR_ALIAS_MAP",
]
