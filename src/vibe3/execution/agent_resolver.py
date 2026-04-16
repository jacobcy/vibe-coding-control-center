"""Thin compatibility wrappers for role -> AgentOptions resolution.

The actual policy truth lives in ExecutionRolePolicyService. This module keeps
the existing public helpers so callers can migrate without re-introducing
role-specific config logic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vibe3.execution.execution_role_policy import ExecutionRolePolicyService
from vibe3.models.review_runner import AgentOptions

if TYPE_CHECKING:
    from vibe3.config.settings import VibeConfig
    from vibe3.models.orchestra_config import OrchestraConfig


def resolve_assignee_dispatch_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
) -> AgentOptions:
    """Resolve agent options from shared assignee-dispatch configuration."""
    _ = runtime_config
    ad = config.assignee_dispatch
    if not ad.agent and not ad.backend:
        raise ValueError(
            "No assignee dispatch agent configuration found in "
            "orchestra.assignee_dispatch. Configure assignee_dispatch.agent or "
            "orchestra.assignee_dispatch.backend in settings.yaml."
        )

    return ExecutionRolePolicyService(config).resolve_effective_agent_options("manager")


def resolve_governance_agent_options(config: OrchestraConfig) -> AgentOptions:
    """Resolve governance agent options from orchestra config."""
    return ExecutionRolePolicyService(config).resolve_effective_agent_options(
        "governance"
    )


def resolve_supervisor_agent_options(config: OrchestraConfig) -> AgentOptions:
    """Resolve supervisor agent options from orchestra config."""
    return ExecutionRolePolicyService(config).resolve_effective_agent_options(
        "supervisor"
    )


def resolve_planner_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
) -> AgentOptions:
    """Resolve planner agent options from plan.agent_config."""
    plan_config = runtime_config.plan
    return AgentOptions(
        agent=plan_config.agent_config.agent,
        backend=(
            plan_config.agent_config.backend
            if not plan_config.agent_config.agent
            else None
        ),
        model=(
            plan_config.agent_config.model
            if not plan_config.agent_config.agent
            else None
        ),
        timeout_seconds=plan_config.agent_config.timeout_seconds,
    )


def resolve_executor_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
) -> AgentOptions:
    """Resolve executor agent options from run.agent_config."""
    run_config = runtime_config.run
    return AgentOptions(
        agent=run_config.agent_config.agent,
        backend=(
            run_config.agent_config.backend
            if not run_config.agent_config.agent
            else None
        ),
        model=(
            run_config.agent_config.model if not run_config.agent_config.agent else None
        ),
        timeout_seconds=run_config.agent_config.timeout_seconds,
    )


def resolve_reviewer_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
) -> AgentOptions:
    """Resolve reviewer agent options from review.agent_config."""
    review_config = runtime_config.review
    return AgentOptions(
        agent=review_config.agent_config.agent,
        backend=(
            review_config.agent_config.backend
            if not review_config.agent_config.agent
            else None
        ),
        model=(
            review_config.agent_config.model
            if not review_config.agent_config.agent
            else None
        ),
        timeout_seconds=review_config.agent_config.timeout_seconds,
    )


def resolve_manager_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
) -> AgentOptions:
    """Resolve manager agent options."""
    return resolve_assignee_dispatch_agent_options(config, runtime_config)
