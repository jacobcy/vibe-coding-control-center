"""Executor role definition and request builders."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from vibe3.agents.models import CodeagentResult, create_codeagent_command
from vibe3.agents.run_prompt import (
    RunPromptMode,
    describe_run_plan_sections,
    make_run_context_builder,
    make_skill_context_builder,
)
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.config.settings import VibeConfig
from vibe3.execution.codeagent_runner import CodeagentExecutionService
from vibe3.execution.codeagent_support import build_self_invocation
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.issue_role_support import (
    build_issue_sync_spec,
    build_task_flow_branch_resolver,
    resolve_env_overridable_agent_options,
)
from vibe3.execution.prompt_meta import PromptContextMode, build_prompt_meta
from vibe3.execution.role_contracts import EXECUTOR_GATE_CONFIG
from vibe3.execution.role_request_factory import (
    build_role_async_request,
    build_role_sync_request,
)
from vibe3.execution.session_service import load_session_id
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

EXECUTOR_PUBLISH_ROLE = TriggerableRoleDefinition(
    name="executor-publish",
    registry_role="executor",
    worktree=EXECUTOR_GATE_CONFIG,
    trigger_name="run",
    trigger_state=IssueState.MERGE_READY,
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
    refs: dict[str, str] = {}
    if plan_ref:
        refs["plan_ref"] = plan_ref
    if audit_ref:
        refs["audit_ref"] = audit_ref

    target_branch = branch or f"task/issue-{issue.number}"
    if commit_mode:
        command_args = [
            "run",
            "--branch",
            target_branch,
            "--skill",
            "vibe-commit",
            "--no-async",
        ]
        refs["commit_mode"] = "true"
    elif plan_ref:
        command_args = [
            "run",
            "--branch",
            target_branch,
            "--plan",
            plan_ref,
            "--no-async",
        ]
    else:
        command_args = ["run", "--branch", target_branch, "--no-async"]

    return build_role_async_request(
        role="executor",
        config=config,
        issue=issue,
        command_args=command_args,
        worktree_requirement=EXECUTOR_ROLE.worktree,
        branch=branch,
        repo_path=repo_path,
        actor=actor,
        refs=refs,
    )


def build_run_sync_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    flow_state: dict[str, object] | None,
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
    show_prompt: bool,
) -> ExecutionRequest:
    """Build the executor sync execution request."""
    store = SQLiteClient()
    flow_state = store.get_flow_state(branch) if branch else None
    meta = build_prompt_meta(
        flow_state,
        ref_keys=("plan_ref", "report_ref", "audit_ref"),
        retry_ref_keys=("report_ref", "audit_ref"),
        session_id=session_id,
        default_mode="coding",
    )
    run_config = getattr(config, "run", None)
    run_prompt = run_config.run_prompt if run_config else None
    task = (
        run_prompt or f"Execute implementation for issue #{issue.number}: {issue.title}"
    )
    summary_sections = describe_run_plan_sections(
        meta.prompt_mode,  # type: ignore[arg-type]
        meta.context_mode,
    )
    refs = dict(meta.refs)
    plan_ref = refs.get("plan_ref")
    audit_ref = refs.get("audit_ref")
    dry_run_summary = meta.summary(summary_sections)
    fallback_prompt = None
    if meta.fallback_context_mode is not None:
        fallback_prompt = make_run_context_builder(
            plan_ref,
            VibeConfig.get_defaults(),
            audit_file=audit_ref,
            mode=meta.prompt_mode,  # type: ignore[arg-type]
            context_mode=meta.fallback_context_mode,
        )()

    return build_role_sync_request(
        role="executor",
        config=config,
        issue=issue,
        branch=branch,
        prompt=make_run_context_builder(
            plan_ref,
            VibeConfig.get_defaults(),
            audit_file=audit_ref,
            mode=meta.prompt_mode,  # type: ignore[arg-type]
            context_mode=meta.context_mode,
        )(),
        task=task,
        options=options,
        worktree_requirement=EXECUTOR_ROLE.worktree,
        session_id=session_id,
        actor=actor,
        dry_run=dry_run,
        show_prompt=show_prompt,
        include_global_notice=meta.include_global_notice,
        fallback_prompt=fallback_prompt,
        fallback_include_global_notice=True,
        extra_refs={k: str(v) for k, v in refs.items()},
        dry_run_summary=dry_run_summary,
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
        load_orchestra_config(),
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
    show_prompt: bool,
    agent: str | None,
    backend: str | None,
    model: str | None,
    fresh_session: bool = False,
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
            show_prompt=show_prompt,
        )
        return CodeagentExecutionService(config).execute_sync(command)

    run_prompt = config.run.run_prompt if getattr(config, "run", None) else None

    # Derive retry from authoritative refs: if report_ref or audit_ref exists,
    # this is a retry round — use retry prompt material.
    audit_file: str | None = None
    prompt_mode: RunPromptMode = "coding"
    report_ref: str | None = None
    retry_session_id: str | None = None
    context_mode: PromptContextMode = "bootstrap"
    meta = None
    if branch:
        try:
            flow_state = SQLiteClient().get_flow_state(branch)
            if flow_state:
                if flow_state.get("report_ref"):
                    report_ref = str(flow_state["report_ref"])
                if flow_state.get("audit_ref"):
                    audit_file = str(flow_state["audit_ref"])
                retry_session_id = (
                    None
                    if fresh_session
                    else load_session_id("executor", branch=branch)
                )
                meta = build_prompt_meta(
                    flow_state,
                    ref_keys=("plan_ref", "report_ref", "audit_ref"),
                    retry_ref_keys=("report_ref", "audit_ref"),
                    session_id=retry_session_id,
                    default_mode="coding",
                )
                prompt_mode = meta.prompt_mode  # type: ignore[assignment]
                context_mode = meta.context_mode
        except Exception:
            pass
    if meta is None:
        refs_for_summary = {
            k: v
            for k, v in {
                "plan_ref": plan_file,
                "report_ref": report_ref,
                "audit_ref": audit_file,
            }.items()
            if v
        }
        from vibe3.execution.prompt_meta import PromptMeta

        meta = PromptMeta(
            prompt_mode=prompt_mode,
            context_mode=context_mode,
            session_id=retry_session_id,
            refs=refs_for_summary,
        )
    dry_run_summary = meta.summary(
        describe_run_plan_sections(prompt_mode, context_mode)
    )
    fallback_prompt = None
    if prompt_mode == "retry" and context_mode == "resume":
        fallback_prompt = make_run_context_builder(
            plan_file,
            config,
            audit_file=audit_file,
            mode=prompt_mode,
            context_mode="bootstrap",
        )()
        dry_run_summary["fallback_context_mode"] = "bootstrap"
    include_global_notice = not (prompt_mode == "retry" and context_mode == "resume")

    command = create_codeagent_command(
        role="executor",
        context_builder=make_run_context_builder(
            plan_file,
            config,
            audit_file=audit_file,
            mode=prompt_mode,
            context_mode=context_mode,
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
        show_prompt=show_prompt,
        include_global_notice=include_global_notice,
        fallback_prompt=fallback_prompt,
        fallback_include_global_notice=True,
        dry_run_summary=dry_run_summary,
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
    try:
        result = execution_service.execute_sync(command)
    except Exception as exc:
        if not dry_run and no_async and issue_number is not None:
            publish_run_command_failure(
                issue_number=issue_number,
                reason=str(exc) or "Execution aborted",
            )
        raise

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
