"""Executor role definition and request builders."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from vibe3.agents.models import CodeagentResult, create_codeagent_command
from vibe3.agents.run_prompt import (
    RunPromptMode,
    make_run_context_builder,
    make_skill_context_builder,
)
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.execution.codeagent_runner import CodeagentExecutionService
from vibe3.execution.codeagent_support import build_self_invocation
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
    build_issue_sync_spec,
    build_task_flow_branch_resolver,
    resolve_env_overridable_agent_options,
)
from vibe3.execution.role_contracts import EXECUTOR_GATE_CONFIG
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.roles.definitions import TriggerableRoleDefinition
from vibe3.services.issue_failure_service import fail_executor_issue

EXECUTOR_ROLE = TriggerableRoleDefinition(
    name="executor",
    registry_role="executor",
    worktree=EXECUTOR_GATE_CONFIG,
    trigger_name="run",
    trigger_state=IssueState.IN_PROGRESS,
)


def resolve_run_options(config: OrchestraConfig) -> Any:
    """Resolve executor agent options with env override support."""
    from vibe3.execution.agent_resolver import resolve_executor_agent_options

    return resolve_env_overridable_agent_options(
        backend_env_key="VIBE3_EXECUTOR_BACKEND",
        model_env_key="VIBE3_EXECUTOR_MODEL",
        fallback_resolver=lambda: resolve_executor_agent_options(
            config, VibeConfig.get_defaults()
        ),
    )


_MERGE_READY_MARKER = "MERGE_READY_COMMIT"


def check_merge_ready_commit(branch: str) -> bool:
    """Check if handoff current.md contains merge-ready commit marker."""
    try:
        from vibe3.clients.git_client import GitClient
        from vibe3.utils.git_helpers import get_branch_handoff_dir

        git_common = GitClient().get_git_common_dir()
        if not git_common:
            return False
        handoff_dir = get_branch_handoff_dir(git_common, branch)
        current_md = handoff_dir / "current.md"
        if not current_md.exists():
            return False
        return _MERGE_READY_MARKER in current_md.read_text(encoding="utf-8")
    except Exception:
        return False


RUN_BRANCH_RESOLVER = build_task_flow_branch_resolver(
    fallback_branch=lambda _issue_number, current_branch: current_branch
)


def build_run_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    *,
    branch: str | None = None,
    repo_path: Path | None = None,
    plan_ref: str | None = None,
    audit_ref: str | None = None,
    commit_mode: bool = False,
    actor: str = "orchestra:executor",
) -> ExecutionRequest:
    """Build the executor async execution request for dispatch."""
    target_branch = branch or f"task/issue-{issue.number}"
    refs: dict[str, str] = {"issue_number": str(issue.number)}
    if plan_ref:
        refs["plan_ref"] = plan_ref
    if audit_ref:
        refs["audit_ref"] = audit_ref
    if commit_mode:
        command_args = ["run", "--skill", "vibe-commit", "--no-async"]
        refs["commit_mode"] = "true"
    elif plan_ref:
        command_args = ["run", "--plan", plan_ref, "--no-async"]
    else:
        command_args = ["run", "--no-async"]
    return build_issue_async_cli_request(
        role="executor",
        issue=issue,
        target_branch=target_branch,
        command_args=command_args,
        actor=actor,
        execution_name=f"vibe3-executor-issue-{issue.number}",
        refs=refs,
        worktree_requirement=EXECUTOR_ROLE.worktree,
        repo_path=repo_path,
    )


def build_run_sync_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
) -> ExecutionRequest:
    """Build the executor sync execution request."""
    run_config = getattr(config, "run", None)
    run_prompt = run_config.run_prompt if run_config else None
    task = (
        run_prompt or f"Execute implementation for issue #{issue.number}: {issue.title}"
    )

    return build_issue_sync_prompt_request(
        role="executor",
        issue=issue,
        target_branch=branch,
        prompt=task,
        options=options,
        task=task,
        actor=actor,
        execution_name=f"vibe3-executor-issue-{issue.number}",
        session_id=session_id,
        dry_run=dry_run,
        worktree_requirement=EXECUTOR_ROLE.worktree,
    )


def publish_run_command_success(
    *,
    issue_number: int,
    _branch: str,
    _result: object,
) -> None:
    """Record run command success. State transitions are the agent's responsibility.

    The agent receives run_task / output_format from settings.yaml (via
    build_run_standard_sections), which includes the instruction to change
    issue label to state/handoff. Code layer MUST NOT auto-transition state
    (noop-gate-boundary-standard).
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
    from vibe3.domain.events import IssueFailed
    from vibe3.domain.publisher import publish

    publish(
        IssueFailed(
            issue_number=issue_number,
            reason=reason,
            actor="agent:run",
        )
    )


RUN_SYNC_SPEC = build_issue_sync_spec(
    role_name="executor",
    resolve_options=resolve_run_options,
    resolve_branch=RUN_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor: build_run_request(
        config,
        issue,
        actor=actor,
    ),
    build_sync_request=build_run_sync_request,
    failure_handler=lambda issue_number, reason: fail_executor_issue(
        issue_number=issue_number,
        reason=reason,
        actor="agent:run",
    ),
)


def find_skill_file(skill_name: str) -> Path | None:
    """Resolve a skill file from cwd or repo root."""
    cwd_candidate = Path.cwd() / "skills" / skill_name / "SKILL.md"
    if cwd_candidate.exists():
        return cwd_candidate
    try:
        from vibe3.services.flow_service import FlowService

        repo_root = Path(FlowService().get_git_common_dir()).parent
    except Exception:
        repo_root = Path.cwd()
    candidate = repo_root / "skills" / skill_name / "SKILL.md"
    if candidate.exists():
        return candidate
    return None


def resolve_run_mode(
    flow_service: Any,
    branch: str,
    instructions: str | None,
    plan: Path | None,
    skill: str | None,
) -> SimpleNamespace:
    """Resolve run command mode from CLI inputs and flow state."""
    if skill:
        return SimpleNamespace(mode="skill", message=skill, plan_file=None)
    if plan:
        return SimpleNamespace(mode="plan", plan_file=str(plan), message=None)
    if instructions:
        preview = instructions[:60]
        suffix = "..." if len(instructions) > 60 else ""
        return SimpleNamespace(
            mode="lightweight",
            plan_file=None,
            message=f"-> Task: {preview}{suffix}",
        )
    flow = flow_service.get_flow_status(branch)
    if flow and flow.plan_ref:
        return SimpleNamespace(
            mode="flow_plan", plan_file=str(flow.plan_ref), message=None
        )
    raise ValueError(
        "No plan specified.\n"
        "Use one of:\n"
        "  vibe3 run <instructions>        # Lightweight mode\n"
        "  vibe3 run --plan <file>         # With plan file\n"
        "  vibe3 run --skill <name>        # With skill"
    )


def ensure_plan_file_exists(plan_file: str | None) -> None:
    """Validate that a referenced plan file exists."""
    if not plan_file:
        return
    if Path(plan_file).exists():
        return
    raise FileNotFoundError(f"Plan file not found: {plan_file}")


def dispatch_run_command_async(
    *,
    branch: str,
    cli_args: list[str],
    issue_number: int | None,
    execution_name: str,
    handoff_metadata: dict[str, object] | None,
) -> None:
    """Dispatch manual run command asynchronously through execution."""
    refs: dict[str, str] = {}
    if issue_number is not None:
        refs["issue_number"] = str(issue_number)
    if handoff_metadata:
        refs.update({k: str(v) for k, v in handoff_metadata.items()})
    ExecutionCoordinator(
        OrchestraConfig.from_settings(),
        SQLiteClient(),
    ).dispatch_execution(
        ExecutionRequest(
            role="executor",
            target_branch=branch,
            target_id=issue_number or 0,
            execution_name=execution_name,
            cmd=build_self_invocation(cli_args),
            cwd=str(Path.cwd()),
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            refs=refs,
            actor="agent:run",
            mode="async",
        )
    )


def execute_manual_run(
    *,
    config: VibeConfig,
    branch: str,
    issue_number: int | None,
    instructions: str | None,
    plan_file: str | None,
    skill: str | None,
    summary: SimpleNamespace,
    dry_run: bool,
    no_async: bool,
    agent: str | None,
    backend: str | None,
    model: str | None,
) -> CodeagentResult | None:
    """Execute manual run command via role-owned facade."""
    if skill:
        skill_file = find_skill_file(skill)
        if not skill_file:
            raise FileNotFoundError(
                f"Skill '{skill}' not found (skills/{skill}/SKILL.md)"
            )

        skill_content = skill_file.read_text(encoding="utf-8")
        if not dry_run and not no_async:
            dispatch_run_command_async(
                branch=branch,
                cli_args=[
                    "run",
                    "--skill",
                    skill,
                    *([instructions] if instructions else []),
                ],
                issue_number=issue_number,
                execution_name=(
                    f"vibe3-executor-issue-{issue_number}"
                    if issue_number is not None
                    else f"vibe3-executor-{branch.replace('/', '-')}"
                ),
                handoff_metadata={"skill": skill},
            )
            return None
        command = create_codeagent_command(
            role="executor",
            context_builder=make_skill_context_builder(skill_content),
            task=instructions or f"Execute skill: {skill}",
            dry_run=dry_run,
            handoff_kind="run",
            handoff_metadata={"skill": skill},
            agent=agent,
            backend=backend,
            model=model,
            config=config,
            branch=branch,
            issue_number=issue_number,
        )
        return CodeagentExecutionService(config).execute_sync(command)

    run_prompt = config.run.run_prompt if getattr(config, "run", None) else None

    # Read flow-state execution hints for retry/fix routing.
    audit_file: str | None = None
    prompt_mode: RunPromptMode = "coding"
    if branch:
        try:
            flow_state = SQLiteClient().get_flow_state(branch)
            if flow_state:
                if flow_state.get("audit_ref"):
                    audit_file = str(flow_state["audit_ref"])
                if flow_state.get("latest_indicate_action") == "fix":
                    prompt_mode = "fix"
        except Exception:
            pass

    command = create_codeagent_command(
        role="executor",
        context_builder=make_run_context_builder(
            plan_file, config, audit_file=audit_file, mode=prompt_mode
        ),
        task=instructions or run_prompt,
        dry_run=dry_run,
        handoff_kind="run",
        handoff_metadata=(
            {"plan_ref": plan_file, "audit_ref": audit_file}
            if plan_file or audit_file
            else None
        ),
        agent=agent,
        backend=backend,
        model=model,
        config=config,
        branch=branch,
        issue_number=issue_number,
    )

    if not dry_run and not no_async:
        if summary.mode == "plan":
            cli_args = [
                "run",
                "--plan",
                str(plan_file),
                *([instructions] if instructions else []),
            ]
        elif summary.mode == "lightweight":
            cli_args = ["run", *([instructions] if instructions else [])]
        else:
            cli_args = ["run"]
        dispatch_run_command_async(
            branch=branch,
            cli_args=cli_args,
            issue_number=issue_number,
            execution_name=(
                f"vibe3-executor-issue-{issue_number}"
                if issue_number is not None
                else f"vibe3-executor-{branch.replace('/', '-')}"
            ),
            handoff_metadata={"plan_ref": plan_file} if plan_file else None,
        )
        return None

    execution_service = CodeagentExecutionService(config)
    result = execution_service.execute_sync(command)
    if not dry_run and no_async and issue_number is not None:
        if result.success:
            publish_run_command_success(
                issue_number=issue_number,
                _branch=branch,
                _result=result,
            )
        else:
            publish_run_command_failure(
                issue_number=issue_number,
                reason=result.stderr or "Execution failed",
            )
    return result
