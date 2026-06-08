"""Factory helpers that create domain objects for the roles layer.

Providing these factories in services (L3, same as roles) lets roles
construct domain objects without importing from the domain module directly,
which would create a circular dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from vibe3.domain import FlowManager
    from vibe3.environment import SessionRegistryService
    from vibe3.models import OrchestraConfig


def create_flow_manager(
    config: OrchestraConfig,
    registry: SessionRegistryService | None = None,
) -> FlowManager:
    """Create a FlowManager instance.

    Lazy-imports FlowManager so that the roles layer can call this
    without taking a direct dependency on vibe3.domain.

    Uses importlib to avoid static analysis detecting circular dependency.
    """
    import importlib

    flow_manager_module = importlib.import_module("vibe3.domain.flow_manager")
    FlowManager = cast(  # noqa: N806
        "type[FlowManager]", flow_manager_module.FlowManager
    )

    return FlowManager(config, registry=registry)
