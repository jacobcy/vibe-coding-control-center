"""Role resolution utilities for dispatch coordination.

Migrated from orchestra/issue_loader.py to establish domain-first architecture.
Role resolution is domain logic, not orchestra adapter concern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibe3.models.orchestration import IssueState
    from vibe3.roles.definitions import TriggerableRoleDefinition


def find_role_for_state(
    state: "IssueState",
) -> "TriggerableRoleDefinition | None":
    """Find the role definition for a state label.

    Defers registry import to avoid circular dependencies and keep
    domain layer imports lightweight.

    Args:
        state: Issue state label to find role for

    Returns:
        Role definition if found, None otherwise
    """
    # Deferred import to avoid circular dependencies at module load time
    from vibe3.roles.registry import LABEL_DISPATCH_ROLES

    for role in LABEL_DISPATCH_ROLES:
        if role.trigger_state == state:
            return role
    return None
