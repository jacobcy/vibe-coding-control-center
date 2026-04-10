"""Unified role definitions and request builders.

This module provides the single source of truth for all role declarations,
request builders, and role-specific declarative configurations. All runtime
registration and dispatch should import from this module rather than from
execution/ or manager/ directories.
"""

from vibe3.roles.definitions import (
    RoleDefinition,
    TriggerableRoleDefinition,
    TriggerName,
)
from vibe3.roles.manager import (
    HANDOFF_MANAGER_ROLE,
    MANAGER_ROLE,
    build_manager_request,
)
from vibe3.roles.registry import LABEL_DISPATCH_ROLES

__all__ = [
    "HANDOFF_MANAGER_ROLE",
    "LABEL_DISPATCH_ROLES",
    "MANAGER_ROLE",
    "RoleDefinition",
    "TriggerName",
    "TriggerableRoleDefinition",
    "build_manager_request",
]
