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
from vibe3.agents.runner import CodeagentExecutionService
from vibe3.models.review_runner import AgentOptions

if TYPE_CHECKING:
    from vibe3.config.settings import VibeConfig
    from vibe3.orchestra.config import OrchestraConfig


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
        worktree=True,  # Governance runs in temporary worktree
    )

    effective = resolve_effective_agent_options(raw_options)
    sync_models_json(effective)
    return effective


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
        worktree=True,  # Supervisor runs in temporary worktree
    )

    effective = resolve_effective_agent_options(raw_options)
    sync_models_json(effective)
    return effective


def resolve_manager_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
    worktree: bool = False,
) -> AgentOptions:
    """Resolve agent options from orchestra assignee dispatch config.

    This is the shared source of truth for manager role resolution,
    used by both async runtime and sync CLI execution.

    Args:
        config: Orchestra configuration with assignee dispatch settings
        runtime_config: Vibe runtime config for fallback defaults
        worktree: Whether to run in worktree mode

    Returns:
        Effective agent options with preset resolved from config/models.json
    """
    ad = config.assignee_dispatch
    raw_options: AgentOptions
    if ad.agent:
        # Use orchestra-specific config if provided
        raw_options = AgentOptions(
            agent=ad.agent,
            backend=ad.backend,
            model=ad.model,
            worktree=worktree,
        )
    else:
        # Fall back to generic run defaults
        raw_options = CodeagentExecutionService(runtime_config).resolve_agent_options(
            "run", worktree=worktree
        )

    # Resolve preset mapping from config/models.json and sync to ~/.codeagent
    effective = resolve_effective_agent_options(raw_options)
    sync_models_json(effective)
    return effective
