"""Executor role helpers and definitions."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from vibe3.config import EXECUTOR_GATE_CONFIG, load_runtime_config
from vibe3.exceptions import UserError
from vibe3.execution import (
    build_task_flow_branch_resolver,
    resolve_env_overridable_agent_options,
)
from vibe3.models import AgentOptions, FlowStatusResponse, IssueState, OrchestraConfig
from vibe3.roles.definitions import RoleOutputContract, TriggerableRoleDefinition
from vibe3.services.flow import FlowService


def validate_run_prerequisites(
    flow_service: FlowService,
    target_branch: str,
) -> tuple[FlowStatusResponse, int | None]:
    """Validate flow exists and return flow status with issue number.

    Args:
        flow_service: FlowService instance for flow operations
        target_branch: Target branch name

    Returns:
        Tuple of (flow status, issue number)

    Raises:
        UserError: If no flow exists for branch
    """
    flow: FlowStatusResponse | None = flow_service.get_flow_status(target_branch)

    if not flow:
        raise UserError(
            f"No flow for branch '{target_branch}'.\n"
            "Run 'vibe3 flow update' or 'vibe3 flow bind <issue> --role task' first."
        )

    issue_number: int | None = flow.task_issue_number
    return flow, issue_number


EXECUTOR_ROLE = TriggerableRoleDefinition(
    name="executor",
    registry_role="executor",
    worktree=EXECUTOR_GATE_CONFIG,
    trigger_name="run",
    trigger_state=IssueState.IN_PROGRESS,
    output_contract=RoleOutputContract(),
)

EXECUTOR_PUBLISH_ROLE = TriggerableRoleDefinition(
    name="executor-publish",
    registry_role="executor",
    worktree=EXECUTOR_GATE_CONFIG,
    trigger_name="run",
    trigger_state=IssueState.MERGE_READY,
    output_contract=RoleOutputContract(),
)


def resolve_run_options(
    config: OrchestraConfig,
    cli_overrides: dict[str, str] | None = None,
) -> Any:
    """Resolve executor agent options with env override support."""
    runtime_config = load_runtime_config(cli_overrides=cli_overrides)

    return resolve_env_overridable_agent_options(
        backend_env_key="VIBE3_EXECUTOR_BACKEND",
        model_env_key="VIBE3_EXECUTOR_MODEL",
        fallback_resolver=lambda: AgentOptions(
            agent=runtime_config.run.agent_config.agent,
            backend=(
                runtime_config.run.agent_config.backend
                if not runtime_config.run.agent_config.agent
                else None
            ),
            model=(
                runtime_config.run.agent_config.model
                if not runtime_config.run.agent_config.agent
                else None
            ),
            timeout_seconds=runtime_config.run.agent_config.timeout_seconds,
        ),
    )


RUN_BRANCH_RESOLVER = build_task_flow_branch_resolver(
    fallback_branch=lambda _issue_number, current_branch: current_branch
)


def publish_run_command_success(
    *,
    issue_number: int,
    _branch: str,
    _result: object,
) -> None:
    """Record run command success. State transitions are the agent's responsibility.

    The agent receives run_task / output_format from config/prompts/prompts.yaml
    (via run.skill recipe with standard providers), which includes the instruction
    to change issue label to state/handoff. Code layer MUST NOT auto-transition
    state (noop-gate-boundary-standard).
    """
    from loguru import logger as _logger

    _logger.bind(
        domain="run",
        event="run_command_success",
        issue=issue_number,
    ).info(
        "Run command completed successfully. "
        "Agent should handle state transition via run_task instructions."
    )


def publish_run_command_failure(
    *,
    issue_number: int,
    reason: str,
) -> None:
    """Publish run failure lifecycle for command-mode execution."""
    from vibe3.services.shared import emit_issue_failed

    emit_issue_failed(issue_number=issue_number, reason=reason, actor="agent:run")


def resolve_run_mode(
    flow_service: Any,
    branch: str,
    instructions: str | None,
    plan: Path | None,
    skill: str | None,
) -> SimpleNamespace:
    """Resolve run command mode from CLI inputs and flow state."""
    if skill:
        return SimpleNamespace(
            mode="skill", message=skill, plan_file=None, worktree_root=None, branch=None
        )
    if plan:
        return SimpleNamespace(
            mode="plan",
            plan_file=str(plan),
            message=None,
            worktree_root=None,
            branch=None,
        )
    if instructions:
        preview = instructions[:60]
        suffix = "..." if len(instructions) > 60 else ""
        return SimpleNamespace(
            mode="lightweight",
            plan_file=None,
            message=f"-> Task: {preview}{suffix}",
            worktree_root=None,
            branch=None,
        )
    flow = flow_service.get_flow_status(branch)
    if flow and flow.plan_ref:
        return SimpleNamespace(
            mode="flow_plan",
            plan_file=str(flow.plan_ref),
            message=None,
            worktree_root=flow.worktree_root,
            branch=branch,
        )
    raise ValueError(
        "No plan specified.\n"
        "Use one of:\n"
        "  vibe3 run <instructions>        # Lightweight mode\n"
        "  vibe3 run --plan <file>         # With plan file\n"
        "  vibe3 run --skill <name>        # With skill"
    )


def ensure_plan_file_exists(
    plan_file: str | None,
    branch: str | None = None,
) -> None:
    """Validate that a referenced plan file exists.

    Uses the same resolution logic as ``vibe3 handoff show`` via
    ``resolve_handoff_target`` to correctly handle worktree-relative paths.
    """
    if not plan_file:
        return
    if Path(plan_file).is_absolute() and Path(plan_file).exists():
        return
    # Import via public API for cross-module call (allows test patching)
    from vibe3.services.handoff import resolve_handoff_target

    try:
        resolve_handoff_target(plan_file, branch=branch)
    except FileNotFoundError as exc:
        raise FileNotFoundError(str(exc)) from exc
