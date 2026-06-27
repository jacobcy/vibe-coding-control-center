"""Factory function for governance functions bundle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vibe3.prompts import build_governance_execution_name
from vibe3.roles.governance import (
    build_governance_snapshot_context,
    render_governance_prompt,
    resolve_governance_options,
)

if TYPE_CHECKING:
    from vibe3.execution import GovernanceFunctions


def build_default_governance_fns() -> GovernanceFunctions:
    """Build default GovernanceFunctions implementation.

    Returns an object that implements the GovernanceFunctions protocol
    by wrapping the concrete governance role functions.
    """

    class _DefaultGovernanceFns:
        """Default implementation wrapping governance role functions."""

        def build_snapshot_context(
            self,
            snapshot: Any,
            *,
            config: Any = None,
            tick_count: int = 0,
            execution_count: int = 0,
            material_override: str | None = None,
            **kwargs: Any,
        ) -> dict[str, Any]:
            return build_governance_snapshot_context(
                snapshot,
                config=config,
                tick_count=tick_count,
                execution_count=execution_count,
                material_override=material_override,
                **kwargs,
            )

        def render_prompt(
            self,
            config: Any,
            snapshot_context: dict[str, Any],
            *,
            tick_count: int = 0,
            execution_count: int = 0,
            material_override: str | None = None,
            **kwargs: Any,
        ) -> Any:
            return render_governance_prompt(
                config,
                snapshot_context,
                tick_count=tick_count,
                execution_count=execution_count,
                material_override=material_override,
                **kwargs,
            )

        def resolve_options(self, config: Any) -> Any:
            return resolve_governance_options(config)

        def build_execution_name(self, tick_count: int, material: str | None = None) -> str:
            return build_governance_execution_name(tick_count, material=material)

    return _DefaultGovernanceFns()
