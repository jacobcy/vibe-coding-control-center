"""Actor normalization utilities for display and PR body rendering.

This module re-exports normalize_actor from vibe3.models._actor_utils
to maintain backward compatibility while ensuring a single source of truth.

The canonical implementation lives in vibe3.models._actor_utils (models layer),
and this module provides a convenient import path for other layers.
"""

# Re-export from canonical location in models layer
from vibe3.models._actor_utils import (
    _ACTOR_ALIAS_MAP,
    _DISPLAY_PLACEHOLDER_ACTORS,
    _PLACEHOLDER_ACTORS,
    normalize_actor,
)

__all__ = [
    "normalize_actor",
    "_PLACEHOLDER_ACTORS",
    "_DISPLAY_PLACEHOLDER_ACTORS",
    "_ACTOR_ALIAS_MAP",
]
