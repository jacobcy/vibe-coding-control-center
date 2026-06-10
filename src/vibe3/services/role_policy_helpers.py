"""Re-export shim for role policy helpers.

The actual implementation has moved to
vibe3.services.shared.roles.
"""

from vibe3.services.shared.roles import get_role_block_function

__all__ = ["get_role_block_function"]
