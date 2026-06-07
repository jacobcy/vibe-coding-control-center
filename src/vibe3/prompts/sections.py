"""Shared prompt section builders.

Public API:
- ``build_tools_guide_section`` — build tools guide section from file
- ``resolve_common_rules_path`` — resolve common rules path from config or resolver
"""

from __future__ import annotations

from typing import cast

from loguru import logger

from vibe3.clients import resolve_runtime_asset
from vibe3.config import ConventionResolver


def build_tools_guide_section(tools_guide_path: str | None) -> str | None:
    """Build tools guide section from file.

    Source: config/v3/settings.yaml (review.common_rules)

    Args:
        tools_guide_path: Path to tools guide file (optional)

    Returns:
        Tools guide section or None if not configured/available
    """
    if not tools_guide_path:
        return None

    log = logger.bind(domain="context_builder", action="build_tools_guide_section")
    path = resolve_runtime_asset(tools_guide_path)
    if not path.exists():
        return None

    try:
        tools_guide = path.read_text(encoding="utf-8")
        log.success("Tools guide section built")
        return f"## Available Tools\n\n{tools_guide}"
    except OSError as e:
        log.bind(error=str(e), path=str(tools_guide_path)).warning(
            "Could not read tools guide"
        )
        return None


def resolve_common_rules_path(
    agent_common_rules: str | None,
    resolver: ConventionResolver,
) -> str | None:
    """Resolve common rules path from agent config or convention resolver fallback.

    Args:
        agent_common_rules: Configured common rules path from agent config
        resolver: Convention resolver for fallback policy path resolution

    Returns:
        Resolved common rules path or None
    """
    if agent_common_rules is not None:
        return agent_common_rules
    # Cast needed: lazy __getattr__ import loses type info
    return cast(str | None, resolver.get_policy_path("common"))
