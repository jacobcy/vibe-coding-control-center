"""Role mapping for orchestra dispatch.

This module provides the dispatch role mappings needed by orchestra layer,
eliminating direct dependency on roles.registry which could cause circular imports.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.roles.definitions import TriggerableRoleDefinition


def get_label_dispatch_roles() -> tuple["TriggerableRoleDefinition", ...]:
    """Get the label dispatch roles.

    Uses lazy import to avoid circular dependency at module load time.
    """
    from vibe3.roles.registry import LABEL_DISPATCH_ROLES

    return LABEL_DISPATCH_ROLES


def find_role_for_state(
    state: "IssueState",
) -> "TriggerableRoleDefinition | None":
    """Find the role definition for a state label.

    Args:
        state: The issue state to find a role for

    Returns:
        The matching TriggerableRoleDefinition, or None if not found
    """
    for role in get_label_dispatch_roles():
        if role.trigger_state == state:
            return role
    return None


# Import IssueState at module level for type checking
if TYPE_CHECKING:
    from vibe3.models.orchestration import IssueState
