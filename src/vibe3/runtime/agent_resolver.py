"""Resolve agent options for orchestra-managed roles.

This module provides role-specific agent resolution that is independent
from the run/plan/review defaults, ensuring manager, supervisor, and
governance have their own configuration truth.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vibe3.agents.backends.codeagent_config import (
    resolve_effective_agent_options,
    sync_models_json,
)
from vibe3.models.review_runner import AgentOptions

if TYPE_CHECKING:
    from vibe3.config.settings import VibeConfig
    from vibe3.models.orchestra_config import OrchestraConfig


def _resolve_and_sync(raw_options: AgentOptions) -> AgentOptions:
    """Resolve preset and sync to ~/.codeagent/models.json."""
    effective = resolve_effective_agent_options(raw_options)
    sync_models_json(effective)
    return effective


def resolve_governance_agent_options(config: OrchestraConfig) -> AgentOptions:
    """Resolve agent options from governance-specific config.

    Args:
        config: Orchestra configuration with governance settings

    Returns:
        Effective agent options with preset resolved from config/models.json
    """
    gov = config.governance
    raw_options = AgentOptions(
        agent=gov.agent,
        backend=gov.backend,
        model=gov.model,
    )

    return _resolve_and_sync(raw_options)


def resolve_supervisor_agent_options(config: OrchestraConfig) -> AgentOptions:
    """Resolve agent options from supervisor-handoff-specific config.

    Args:
        config: Orchestra configuration with supervisor handoff settings

    Returns:
        Effective agent options with preset resolved from config/models.json
    """
    handoff = config.supervisor_handoff
    raw_options = AgentOptions(
        agent=handoff.agent,
        backend=handoff.backend,
        model=handoff.model,
    )

    return _resolve_and_sync(raw_options)


def resolve_planner_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
) -> AgentOptions:
    """Resolve agent options for planner role.

    Planner shares the same assignee_dispatch configuration as manager,
    since both operate within the same orchestra context.

    Args:
        config: Orchestra configuration with assignee dispatch settings
        runtime_config: Unused compatibility parameter kept for existing callers

    Returns:
        Effective agent options with preset resolved from config/models.json
    """
    return resolve_manager_agent_options(config, runtime_config)


def resolve_executor_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
) -> AgentOptions:
    """Resolve agent options for executor role.

    Executor shares the same assignee_dispatch configuration as manager,
    since both operate within the same orchestra context.

    Args:
        config: Orchestra configuration with assignee dispatch settings
        runtime_config: Unused compatibility parameter kept for existing callers

    Returns:
        Effective agent options with preset resolved from config/models.json
    """
    return resolve_manager_agent_options(config, runtime_config)


def resolve_reviewer_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
) -> AgentOptions:
    """Resolve agent options for reviewer role.

    Reviewer shares the same assignee_dispatch configuration as manager,
    since both operate within the same orchestra context.

    Args:
        config: Orchestra configuration with assignee dispatch settings
        runtime_config: Unused compatibility parameter kept for existing callers

    Returns:
        Effective agent options with preset resolved from config/models.json
    """
    return resolve_manager_agent_options(config, runtime_config)


def resolve_manager_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
) -> AgentOptions:
    """Resolve agent options from orchestra assignee dispatch config.

    This is the shared source of truth for manager role resolution,
    used by both async runtime and sync CLI execution.

    Resolution order:
    1. assignee_dispatch.agent          -> preset mode
    2. assignee_dispatch.backend/model  -> backend direct mode

    If assignee_dispatch contains both ``agent`` and ``backend/model``,
    manager execution intentionally prefers ``agent`` as the primary entry.
    After that, ``resolve_effective_agent_options`` may resolve the preset into an
    explicit backend/model, so an additional ``model`` value can still influence
    the final model selection even when ``agent`` is present.

    Args:
        config: Orchestra configuration with assignee dispatch settings
        runtime_config: Unused compatibility parameter kept for existing callers

    Returns:
        Effective agent options with preset resolved from config/models.json
    """
    _ = runtime_config
    ad = config.assignee_dispatch
    if not ad.agent and not ad.backend:
        raise ValueError(
            "No manager agent configuration found in orchestra.assignee_dispatch. "
            "Configure assignee_dispatch.agent or assignee_dispatch.backend in "
            "settings.yaml."
        )

    raw_options = AgentOptions(
        agent=ad.agent,
        backend=ad.backend,
        model=ad.model,
        timeout_seconds=ad.timeout_seconds,
    )

    # Resolve preset mapping from config/models.json and sync to ~/.codeagent
    return _resolve_and_sync(raw_options)
