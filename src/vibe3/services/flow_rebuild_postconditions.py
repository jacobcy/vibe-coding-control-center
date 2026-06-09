"""Re-export shim — rebuild postconditions moved to flow.rebuild_postconditions."""

from vibe3.services.flow.rebuild_postconditions import assert_rebuild_postconditions

__all__ = ["assert_rebuild_postconditions"]
