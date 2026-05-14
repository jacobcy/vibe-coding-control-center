"""Thin compatibility wrappers for role -> AgentOptions resolution.

DEPRECATED: Use ExecutionRolePolicyService directly instead of these wrappers.
This module will be removed in a future version.
"""

from __future__ import annotations

import warnings
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
    """Resolve agent options from shared assignee-dispatch configuration.

    .. deprecated::
        Use ExecutionRolePolicyService(config).resolve_effective_agent_options(
            "manager"
        ) instead.
    """
    warnings.warn(
        "resolve_assignee_dispatch_agent_options is deprecated. "
        "Use ExecutionRolePolicyService(config).resolve_effective_agent_options("
        "'manager') instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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
    """Resolve governance agent options from orchestra config.

    .. deprecated::
        Use ExecutionRolePolicyService(config).resolve_effective_agent_options(
            "governance"
        ) instead.
    """
    warnings.warn(
        "resolve_governance_agent_options is deprecated. "
        "Use ExecutionRolePolicyService(config).resolve_effective_agent_options("
        "'governance') instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return ExecutionRolePolicyService(config).resolve_effective_agent_options(
        "governance"
    )


def resolve_supervisor_agent_options(config: OrchestraConfig) -> AgentOptions:
    """Resolve supervisor agent options from orchestra config.

    .. deprecated::
        Use ExecutionRolePolicyService(config).resolve_effective_agent_options(
            "supervisor"
        ) instead.
    """
    warnings.warn(
        "resolve_supervisor_agent_options is deprecated. "
        "Use ExecutionRolePolicyService(config).resolve_effective_agent_options("
        "'supervisor') instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return ExecutionRolePolicyService(config).resolve_effective_agent_options(
        "supervisor"
    )


def resolve_planner_agent_options(
    config: OrchestraConfig,
    runtime_config: VibeConfig,
) -> AgentOptions:
    """Resolve planner agent options from plan.agent_config.

    .. deprecated::
        Use ExecutionRolePolicyService or directly construct AgentOptions from
        runtime_config.plan.agent_config instead.
    """
    warnings.warn(
        "resolve_planner_agent_options is deprecated. "
        "Directly construct AgentOptions from runtime_config.plan.agent_config "
        "instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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
    """Resolve executor agent options from run.agent_config.

    .. deprecated::
        Use ExecutionRolePolicyService or directly construct AgentOptions from
        runtime_config.run.agent_config instead.
    """
    warnings.warn(
        "resolve_executor_agent_options is deprecated. "
        "Directly construct AgentOptions from runtime_config.run.agent_config "
        "instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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
    """Resolve reviewer agent options from review.agent_config.

    .. deprecated::
        Use ExecutionRolePolicyService or directly construct AgentOptions from
        runtime_config.review.agent_config instead.
    """
    warnings.warn(
        "resolve_reviewer_agent_options is deprecated. "
        "Directly construct AgentOptions from runtime_config.review.agent_config "
        "instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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
    """Resolve manager agent options.

    .. deprecated::
        Use ExecutionRolePolicyService(config).resolve_effective_agent_options(
            "manager"
        ) instead.
    """
    warnings.warn(
        "resolve_manager_agent_options is deprecated. "
        "Use ExecutionRolePolicyService(config).resolve_effective_agent_options("
        "'manager') instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return resolve_assignee_dispatch_agent_options(config, runtime_config)
