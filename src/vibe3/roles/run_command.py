"""Executor command execution logic."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from vibe3.agents import (
    CodeagentResult,
    RunPromptMode,
    create_codeagent_command,
    describe_run_plan_sections,
    make_run_context_builder,
    make_skill_context_builder,
)
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.config.settings import VibeConfig
from vibe3.exceptions import SkillNotAvailableError
from vibe3.execution.codeagent_runner import CodeagentExecutionService
from vibe3.execution.codeagent_support import build_self_invocation
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.prompt_meta import build_prompt_meta
from vibe3.execution.session_service import load_session_id
from vibe3.models.execution_request import ExecutionRequest
from vibe3.models.prompt_meta import PromptContextMode
from vibe3.models.worktree import WorktreeRequirement
from vibe3.roles.run_helpers import (
    publish_run_command_failure,
    publish_run_command_success,
)
from vibe3.services.convention_resolver import ConventionResolver
from vibe3.services.error_helpers import record_dispatch_failure_if_unexpected


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
        resolver = ConventionResolver.from_repo()
    return resolver.get_skill_path(skill)


def dispatch_run_command_async(
    *,
    branch: str,
    cli_args: list[str],
    issue_number: int | None,
    execution_name: str,
    handoff_metadata: dict[str, object] | None,
) -> None:
    """Dispatch manual run command asynchronously through execution."""
    from vibe3.execution.issue_role_support import resolve_orchestra_repo_root

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
        skill_path = resolve_skill_path(skill)
        if not skill_path:
            raise SkillNotAvailableError(skill)

        # Resolve relative path against repo root for CWD-independent access
        from vibe3.clients.git_client import GitClient

        try:
            git_client = GitClient()
            git_common_dir = git_client.get_git_common_dir()
            if git_common_dir:
                repo_root = Path(git_common_dir).parent
                abs_skill_path = repo_root / skill_path
            else:
                # Fallback to cwd-relative if not in git repo
                abs_skill_path = Path(skill_path)
            skill_content = abs_skill_path.read_text(encoding="utf-8")
        except OSError as e:
            raise ValueError(f"Failed to read skill file '{skill_path}': {e}") from e
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
