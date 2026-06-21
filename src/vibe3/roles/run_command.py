"""Executor command execution logic."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.config import ConventionResolver

from vibe3.agents import (
    CodeagentResult,
    RunPromptMode,
    create_codeagent_command,
    describe_run_plan_sections,
    make_publish_context_builder,
    make_run_context_builder,
    make_skill_context_builder,
)
from vibe3.clients import SQLiteClient, resolve_runtime_asset
from vibe3.config import (
    RoleCliOverrides,
    VibeConfig,
    get_resolver,
    load_orchestra_config,
)
from vibe3.exceptions import SkillNotAvailableError
from vibe3.execution import (
    CodeagentExecutionService,
    ExecutionCoordinator,
    build_prompt_meta,
    build_self_invocation,
    load_session_id,
)
from vibe3.models import ExecutionRequest, PromptContextMode, WorktreeRequirement
from vibe3.roles.run_helpers import (
    publish_run_command_failure,
    publish_run_command_success,
)
from vibe3.services.orchestra import record_dispatch_failure_if_unexpected


@dataclass
class AsyncDispatchResult:
    """Result of async dispatch operation."""

    tmux_session: str | None
    log_path: str | None


def resolve_skill_path(
    skill: str, resolver: ConventionResolver | None = None
) -> str | None:
    """Resolve skill SKILL.md path through profile.

    Args:
        skill: Skill name
        resolver: Optional resolver (uses from_repo() if None)

    Returns:
        Path or None if not found

    Example:
        >>> path = resolve_skill_path("vibe-commit")
        >>> if path:
        ...     content = Path(path).read_text()
    """
    if resolver is None:
        resolver = get_resolver()
    result: str | None = resolver.get_skill_path(skill)
    return result


def dispatch_run_command_async(
    *,
    branch: str,
    cli_args: list[str],
    issue_number: int | None,
    execution_name: str,
    handoff_metadata: dict[str, object] | None,
) -> AsyncDispatchResult:
    """Dispatch manual run command asynchronously through execution."""
    from vibe3.execution import resolve_orchestra_repo_root

    refs: dict[str, str] = {}
    if issue_number is not None:
        refs["issue_number"] = str(issue_number)
    if handoff_metadata:
        refs.update({k: str(v) for k, v in handoff_metadata.items()})

    # Resolve repo path from git common dir (main repo root)
    repo_root = resolve_orchestra_repo_root()

    launch = ExecutionCoordinator(
        load_orchestra_config(),
        SQLiteClient(),
    ).dispatch_execution(
        ExecutionRequest(
            role="executor",
            target_branch=branch,
            target_id=issue_number or 0,
            execution_name=execution_name,
            cmd=build_self_invocation(cli_args),
            cwd=None,  # Let coordinator resolve worktree path
            repo_path=str(repo_root),
            worktree_requirement=WorktreeRequirement.PERMANENT,
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            refs=refs,
            actor="agent:run",
            mode="async",
        )
    )
    record_dispatch_failure_if_unexpected(
        result=launch,
        role="executor",
        issue_number=issue_number,
        branch=branch,
    )

    return AsyncDispatchResult(
        tmux_session=launch.tmux_session,
        log_path=launch.log_path,
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
    publish: bool = False,
    prompts_path: Path | None = None,
) -> CodeagentResult | None:
    """Execute manual run command via role-owned facade."""
    if skill:
        skill_path = resolve_skill_path(skill)
        if not skill_path:
            from vibe3.config import diagnose_profile

            detected_profile = diagnose_profile()
            raise SkillNotAvailableError(skill, profile=detected_profile)

        try:
            abs_skill_path = resolve_runtime_asset(skill_path)
            skill_content = abs_skill_path.read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError(f"Failed to read skill file '{skill_path}': {e}") from e
        if not dry_run and not no_async:
            cli_args = (
                [
                    "run",
                    "--publish",
                    *([instructions] if instructions else []),
                ]
                if publish
                else [
                    "run",
                    "--skill",
                    skill,
                    *([instructions] if instructions else []),
                ]
            )
            # Forward CLI override args to async child
            overrides = RoleCliOverrides(
                agent=agent, backend=backend, model=model, fresh_session=fresh_session
            )
            cli_args += overrides.to_argv()
            handoff_metadata: dict[str, object] = {"skill": skill}
            if publish:
                handoff_metadata["publish"] = True
            dispatch_result = dispatch_run_command_async(
                branch=branch,
                cli_args=cli_args,
                issue_number=issue_number,
                execution_name=(
                    f"vibe3-executor-issue-{issue_number}"
                    if issue_number is not None
                    else f"vibe3-executor-{branch.replace('/', '-')}"
                ),
                handoff_metadata=handoff_metadata,
            )
            if dispatch_result.tmux_session:
                logger.info(f"tmux session: {dispatch_result.tmux_session}")
            if dispatch_result.log_path:
                logger.info(f"log: {dispatch_result.log_path}")
            return None

        # Check if this is a publish path execution
        # Two entry points:
        # 1. Manual: --publish flag (publish=True)
        # 2. Automatic: commit_mode from flow_state
        is_publish_path = False

        # Manual channel: explicit --publish flag
        if publish:
            is_publish_path = True
        # Automatic channel: commit_mode detection from flow_state
        elif branch:
            try:
                flow_state = SQLiteClient().get_flow_state(branch)
                if flow_state:
                    commit_mode = flow_state.get("commit_mode")
                    # Validate commit_mode is boolean to prevent type coercion issues
                    is_publish_path = (
                        bool(commit_mode) if isinstance(commit_mode, bool) else False
                    )
            except Exception as e:
                # Log unexpected errors but don't fail execution - graceful degradation
                # Falls back to skill builder, which noop gate will catch if wrong
                logger.warning(
                    f"Unexpected error checking flow_state for publish path: {e}. "
                    "Defaulting to skill builder. Noop gate will catch if "
                    "wrong recipe used."
                )

        # Use publish-specific context builder for commit_mode execution
        context_builder = (
            make_publish_context_builder(skill_content)
            if is_publish_path
            else make_skill_context_builder(skill_content)
        )

        command = create_codeagent_command(
            role="executor",
            context_builder=context_builder,
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
        from vibe3.execution import PromptMeta

        meta = PromptMeta(
            prompt_mode=prompt_mode,
            context_mode=context_mode,
            session_id=retry_session_id,
            refs=refs_for_summary,
        )
    dry_run_summary = meta.summary(
        describe_run_plan_sections(prompt_mode, context_mode, prompts_path=prompts_path)
    )
    fallback_prompt = None
    if prompt_mode == "retry" and context_mode == "resume":
        fallback_prompt = make_run_context_builder(
            plan_file,
            config,
            audit_file=audit_file,
            mode=prompt_mode,
            context_mode="bootstrap",
            prompts_path=prompts_path,
            annotate_sections=dry_run,
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
            prompts_path=prompts_path,
            annotate_sections=dry_run,
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
        # Forward CLI override args to async child
        overrides = RoleCliOverrides(
            agent=agent, backend=backend, model=model, fresh_session=fresh_session
        )
        cli_args += overrides.to_argv()
        dispatch_result = dispatch_run_command_async(
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
        if dispatch_result.tmux_session:
            logger.info(f"tmux session: {dispatch_result.tmux_session}")
        if dispatch_result.log_path:
            logger.info(f"log: {dispatch_result.log_path}")
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
