"""Runtime-kernel taxonomy: module categories and dependency rules.

This module is the single source of truth for the horizontal category
mapping within the L3 orchestration core. It is consumed by modularity
tests and may be referenced by downstream cleanup issues.

The taxonomy defines five horizontal categories within L3:
- KERNEL: Runtime kernel (heartbeat, service lifecycle)
- COMMAND_ADAPTER: Execution adapters and application use cases
- POLICY: Role definitions (declarative dispatch predicates & material loading)
- PLUGIN_SURFACE: Extension points (backward-compat adapters, user-facing hooks)
- OBSERVATION: Event core (domain events, handlers, observation facade)

Dependencies flow downward through categories: Kernel (1) must not depend on
Adapter (2), Policy (3), Plugin (4), or Observation (5) internals. Observation
(5) may depend on all categories.
"""

from enum import IntEnum
from typing import Final


class ModuleCategory(IntEnum):
    """Horizontal category within the L3 orchestration core."""

    KERNEL = 1  # Runtime kernel: heartbeat, service lifecycle
    COMMAND_ADAPTER = (
        2  # Execution shell: translates domain intents to backend commands
    )
    POLICY = 3  # Role definitions: declarative dispatch predicates & material loading
    PLUGIN_SURFACE = 4  # Extension points: backward-compat adapters, user-facing hooks
    OBSERVATION = 5  # Event core: domain events, handlers, observation facade
    # Infrastructure (L6) and gateway (L2) modules are outside this taxonomy


# Map each L3 module to its category
MODULE_CATEGORY_MAP: Final[dict[str, ModuleCategory]] = {
    "runtime": ModuleCategory.KERNEL,
    "execution": ModuleCategory.COMMAND_ADAPTER,
    "roles": ModuleCategory.POLICY,
    "orchestra": ModuleCategory.PLUGIN_SURFACE,
    "domain": ModuleCategory.OBSERVATION,
    # application use cases — same tier as execution adapters
    "services": ModuleCategory.COMMAND_ADAPTER,
}

# Allowed dependency directions: category N may import from categories >= N
# Kernel (1) must not import from command-adapter (2), policy (3),
# plugin (4), observation (5) internals
# Observation (5) may import from all categories (event core needs full access)
# Plugin-surface (4) may import from kernel, adapter, policy, and itself
CATEGORY_ALLOWED_DEPS: Final[dict[ModuleCategory, set[ModuleCategory]]] = {
    ModuleCategory.KERNEL: {ModuleCategory.KERNEL},
    ModuleCategory.COMMAND_ADAPTER: {
        ModuleCategory.KERNEL,
        ModuleCategory.COMMAND_ADAPTER,
    },
    ModuleCategory.POLICY: {
        ModuleCategory.KERNEL,
        ModuleCategory.COMMAND_ADAPTER,
        ModuleCategory.POLICY,
    },
    ModuleCategory.PLUGIN_SURFACE: {
        ModuleCategory.KERNEL,
        ModuleCategory.COMMAND_ADAPTER,
        ModuleCategory.POLICY,
        ModuleCategory.PLUGIN_SURFACE,
    },
    ModuleCategory.OBSERVATION: {
        ModuleCategory.KERNEL,
        ModuleCategory.COMMAND_ADAPTER,
        ModuleCategory.POLICY,
        ModuleCategory.PLUGIN_SURFACE,
        ModuleCategory.OBSERVATION,
    },
}
