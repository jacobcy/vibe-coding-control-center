"""Reviewer role definition and request builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast

import typer
from loguru import logger

from vibe3.agents import (
    build_review_prompt_body,
    create_codeagent_command,
    describe_review_sections,
    make_review_context_builder,
)
from vibe3.analysis import build_change_analysis, build_snapshot_diff, changed_symbols

# public-api: pending upstream export
from vibe3.config import (
    REVIEWER_GATE_CONFIG,
    RoleCliOverrides,
    VibeConfig,
    get_convention,
    load_orchestra_config,
    load_runtime_config,
)
from vibe3.execution import (
    CodeagentExecutionService,
    ExecutionCoordinator,
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
    build_prompt_meta,
    build_self_invocation,
    build_task_flow_branch_resolver,
    resolve_env_overridable_agent_options,
)
from vibe3.models import (
    AgentOptions,
    ExecutionRequest,
    IssueInfo,
    IssueState,
    OrchestraConfig,
    ReviewRequest,
    ReviewScope,
    StructureDiff,
    WorktreeRequirement,
)
from vibe3.roles.definitions import (
    IssueRoleSyncSpec,
    RoleOutputContract,
    TriggerableRoleDefinition,
)
from vibe3.roles.review_helpers import (
    ReviewRunResult,
    finalize_review_output,
)
from vibe3.services.flow import FlowService
from vibe3.services.issue import fail_reviewer_issue
from vibe3.services.orchestra import record_dispatch_failure_if_unexpected


def validate_review_prerequisites(
    flow_service: FlowService,
    branch: str,
) -> tuple[Any, int]:
    """Validate flow exists and has linked issue.

    Args:
        flow_service: FlowService instance for flow operations
        branch: Target branch name

    Returns:
        Tuple of (flow status, issue number)

    Raises:
        UserError: If no flow exists or no linked issue
    """
    from vibe3.exceptions import UserError

    flow = flow_service.get_flow_status(branch)

    if not flow:
        raise UserError(
            f"No flow for branch '{branch}'.\n"
            "Run 'vibe3 flow update' or 'vibe3 flow bind <issue> --role task' first."
        )

    issue_number = flow.task_issue_number

    if not issue_number:
        raise UserError(
            f"No issue linked to flow '{branch}'.\nRun 'vibe3 flow bind <issue>' first."
        )

    return flow, issue_number


REVIEWER_ROLE = TriggerableRoleDefinition(
    name="reviewer",
    registry_role="reviewer",
    worktree=REVIEWER_GATE_CONFIG,
    trigger_name="review",
    trigger_state=IssueState.REVIEW,
    output_contract=RoleOutputContract(requires_verdict=True),
)


def resolve_review_options(
    config: OrchestraConfig,
    cli_overrides: dict[str, str] | None = None,
) -> Any:
    """Resolve reviewer agent options with env override support."""
    runtime_config = load_runtime_config(cli_overrides=cli_overrides)
    return resolve_env_overridable_agent_options(
        backend_env_key="VIBE3_REVIEWER_BACKEND",
        model_env_key="VIBE3_REVIEWER_MODEL",
        fallback_resolver=lambda: AgentOptions(
            agent=runtime_config.review.agent_config.agent,
            backend=(
                runtime_config.review.agent_config.backend
                if not runtime_config.review.agent_config.agent
                else None
            ),
            model=(
                runtime_config.review.agent_config.model
                if not runtime_config.review.agent_config.agent
                else None
            ),
            timeout_seconds=runtime_config.review.agent_config.timeout_seconds,
        ),
    )


REVIEW_BRANCH_RESOLVER = build_task_flow_branch_resolver(
    fallback_branch=lambda _issue_number, current_branch: current_branch
)


def build_issue_review_request(
    issue: IssueInfo,
    *,
    branch: str | None = None,
    report_ref: str | None = None,
    actor: str = "orchestra:reviewer",
    repo_path: Path | None = None,
    sync: bool = False,
    config: OrchestraConfig | None = None,
    session_id: str | None = None,
    options: Any = None,
    dry_run: bool = False,
    show_prompt: bool = False,
    flow_state: dict[str, object] | None = None,
    tick_id: int = 0,
) -> ExecutionRequest:
    """Consolidated factory for issue review requests (async and sync)."""
    convention = get_convention()
    target_branch = branch or convention.branch.canonical_branch(issue.number)
    execution_name = f"vibe3-reviewer-issue-{issue.number}"

    if sync:
        cfg = config or load_orchestra_config()
        review_config = getattr(cfg, "review", None)
        review_prompt = review_config.review_prompt if review_config else None
        task = (
            review_prompt
            or f"Review implementation for issue #{issue.number}: {issue.title}"
        )
        meta = build_prompt_meta(
            flow_state,
            ref_keys=("report_ref", "audit_ref"),
            retry_ref_keys=("audit_ref",),
            session_id=session_id,
            default_mode="first",
        )

        request = ReviewRequest(
            scope=ReviewScope.for_base("origin/main"),
            task_guidance=task,
        )
        prompt = build_review_prompt_body(
            request,
            VibeConfig.get_defaults(),
            mode=meta.prompt_mode,  # type: ignore[arg-type]
            context_mode=meta.context_mode,
        )
        fallback_prompt = None
        if meta.fallback_context_mode is not None:
            fallback_prompt = build_review_prompt_body(
                request,
                VibeConfig.get_defaults(),
                mode=meta.prompt_mode,  # type: ignore[arg-type]
                context_mode=meta.fallback_context_mode,
            )
        sections = describe_review_sections(
            meta.prompt_mode,  # type: ignore[arg-type]
            meta.context_mode,
        )
        refs = dict(meta.refs)
        if report_ref and "report_ref" not in refs:
            refs["report_ref"] = report_ref
        dry_run_summary = meta.summary(sections)

        return build_issue_sync_prompt_request(
            role="reviewer",
            issue=issue,
            target_branch=target_branch,
            prompt=prompt,
            options=options,
            task=task,
            actor=actor,
            execution_name=execution_name,
            session_id=session_id,
            dry_run=dry_run,
            show_prompt=show_prompt,
            include_global_notice=meta.include_global_notice,
            fallback_prompt=fallback_prompt,
            fallback_include_global_notice=True,
            extra_refs=refs,
            dry_run_summary=dry_run_summary,
            worktree_requirement=REVIEWER_ROLE.worktree,
            tick_id=tick_id,
        )

    async_refs: dict[str, str] = {"issue_number": str(issue.number)}
    if report_ref:
        async_refs["report_ref"] = report_ref
    command_args = [
        "review",
        "--branch",
        target_branch,
        "--no-async",
    ]

    return build_issue_async_cli_request(
        role="reviewer",
        issue=issue,
        target_branch=target_branch,
        command_args=command_args,
        actor=actor,
        execution_name=execution_name,
        refs=async_refs,
        worktree_requirement=REVIEWER_ROLE.worktree,
        repo_path=repo_path,
        tick_id=tick_id,
    )


# Compatibility wrappers
def build_review_request(
    config: OrchestraConfig, issue: IssueInfo, **kwargs: Any
) -> ExecutionRequest:
    return build_issue_review_request(issue, **kwargs)


def build_review_sync_request(
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
    from vibe3.clients import SQLiteClient

    flow_state = SQLiteClient().get_flow_state(branch) if branch else None
    return build_issue_review_request(
        issue,
        branch=branch,
        flow_state=flow_state,
        session_id=session_id,
        options=options,
        actor=actor,
        dry_run=dry_run,
        show_prompt=show_prompt,
        sync=True,
        config=config,
    )


REVIEW_SYNC_SPEC = IssueRoleSyncSpec(
    role_name="reviewer",
    resolve_options=resolve_review_options,
    resolve_branch=REVIEW_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor, branch: build_issue_review_request(
        issue,
        branch=branch,
        actor=actor,
    ),
    build_sync_request=build_review_sync_request,
    failure_handler=lambda issue_number, reason: fail_reviewer_issue(
        issue_number=issue_number,
        reason=reason,
    ),
)


def build_manual_review_request_payload(
    scope: ReviewScope,
    *,
    issue_number: int | None = None,
    head_branch: str | None = None,
    source_type: str,
    identifier: str,
    structure_diff: StructureDiff | None = None,
    analysis_runner: Callable[[str, str], dict[str, object]] = build_change_analysis,
) -> tuple[ReviewRequest, int | None, str | None]:
    """Consolidated factory for manual review request payloads (PR and Base)."""
    request = ReviewRequest(
        scope=scope,
        changed_symbols=changed_symbols(analysis_runner(source_type, identifier)),
        structure_diff=structure_diff,
    )
    return request, issue_number, head_branch


def build_base_review_request(
    current_branch: str,
    base_branch: str,
    *,
    flow_service: FlowService | None = None,
    analysis_runner: Callable[[str, str], dict[str, object]] = build_change_analysis,
    snapshot_diff_builder: Callable[
        [str, str | None], object | None
    ] = build_snapshot_diff,
) -> tuple[ReviewRequest, int | None, str | None]:
    """Build request payload for base-branch review."""
    service = flow_service or FlowService()
    flow = service.get_flow_status(current_branch)
    raw_diff = snapshot_diff_builder(base_branch, current_branch)
    return build_manual_review_request_payload(
        scope=ReviewScope.for_base(base_branch),
        issue_number=flow.task_issue_number if flow else None,
        source_type="branch",
        identifier=base_branch,
        structure_diff=(
            cast(StructureDiff | None, raw_diff) if raw_diff is not None else None
        ),
        analysis_runner=analysis_runner,
    )


def execute_manual_review_async(
    *,
    request: ReviewRequest,
    instructions: str | None,
    issue_number: int | None = None,
    pr_number: int | None = None,
    branch: str,
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    fresh_session: bool = False,
) -> ReviewRunResult:
    """Execute manual review in async mode (tmux wrapper)."""
    launch = _dispatch_async_manual_review(
        request=request,
        branch=branch,
        issue_number=issue_number,
        pr_number=pr_number,
        instructions=instructions,
        agent=agent,
        backend=backend,
        model=model,
        fresh_session=fresh_session,
    )
    record_dispatch_failure_if_unexpected(
        result=launch,
        role="reviewer",
        issue_number=issue_number,
        branch=branch,
    )
    if not launch.launched:
        reason_code = launch.reason_code or "unknown"
        if reason_code in ("capacity_full", "duplicate_dispatch"):
            # Normal throttling/dedup - log at info level
            logger.bind(domain="review").info(
                f"Review dispatch throttled: {launch.reason}",
                reason_code=reason_code,
            )
        else:
            # Unexpected failure - log at warning level
            logger.bind(domain="review").warning(
                f"Review dispatch failed unexpectedly: {launch.reason}",
                reason_code=reason_code,
            )
        return ReviewRunResult(
            "ERROR", None, issue_number, launch.tmux_session, launch.log_path
        )
    return ReviewRunResult(
        "ASYNC", None, issue_number, launch.tmux_session, launch.log_path
    )


def execute_manual_review_sync(
    *,
    request: ReviewRequest,
    dry_run: bool,
    instructions: str | None,
    issue_number: int | None = None,
    pr_number: int | None = None,
    branch: str | None = None,
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    fresh_session: bool = False,
    config: VibeConfig | None = None,
    flow_service: FlowService | None = None,
    context_builder: Callable[..., object] = make_review_context_builder,
    show_prompt: bool = False,
) -> ReviewRunResult:
    """Execute manual review in sync mode (direct execution)."""
    from vibe3.execution import load_session_id

    _ = flow_service
    cfg = config or VibeConfig.get_defaults()
    log = logger.bind(domain="review", scope=request.scope.kind)
    task = _build_manual_review_task(cfg, instructions, request, pr_number, log)
    session_id = None if fresh_session else load_session_id("reviewer", branch)
    command = create_codeagent_command(
        role="reviewer",
        context_builder=cast(Callable[[], str], context_builder(request, cfg)),
        task=task,
        dry_run=dry_run,
        handoff_kind="review",
        handoff_metadata={},
        config=cfg,
        branch=branch,
        issue_number=issue_number,
        show_prompt=show_prompt,
        agent=agent,
        backend=backend,
        model=model,
        session_id=session_id,
    )
    result = CodeagentExecutionService(cfg).execute_sync(command)
    if dry_run:
        return ReviewRunResult("DRY_RUN", None, issue_number)

    audit_ref, verdict = finalize_review_output(
        review_output=result.stdout,
        branch=branch,
        actor="agent:review",
    )
    return ReviewRunResult(verdict, audit_ref, issue_number)


def _dispatch_async_manual_review(
    *,
    request: ReviewRequest,
    branch: str,
    issue_number: int | None,
    pr_number: int | None,
    instructions: str | None,
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    fresh_session: bool = False,
) -> Any:
    cli_args = _build_manual_review_async_cli_args(
        request, instructions, agent, backend, model, fresh_session
    )
    target_id = pr_number or issue_number or 0
    execution_name = (
        f"vibe3-reviewer-issue-{target_id}"
        if issue_number is not None
        else f"vibe3-reviewer-{request.scope.kind}-{target_id or 'adhoc'}"
    )
    from vibe3.clients import SQLiteClient
    from vibe3.execution import resolve_orchestra_repo_root

    repo_root = resolve_orchestra_repo_root()

    coordinator = ExecutionCoordinator(
        load_orchestra_config(),
        SQLiteClient(),
    )
    return coordinator.dispatch_execution(
        ExecutionRequest(
            role="reviewer",
            target_branch=branch,
            target_id=target_id,
            execution_name=execution_name,
            cmd=build_self_invocation(cli_args),
            cwd=None,  # Let coordinator resolve worktree path
            repo_path=str(repo_root),
            worktree_requirement=WorktreeRequirement.PERMANENT,
            refs={
                "task": instructions or "",
                "review_scope": request.scope.kind,
                **(
                    {"issue_number": str(issue_number)}
                    if issue_number is not None
                    else {}
                ),
                **({"pr_number": str(pr_number)} if pr_number is not None else {}),
            },
            actor="agent:review",
            mode="async",
        )
    )


def _build_manual_review_async_cli_args(
    request: ReviewRequest,
    instructions: str | None,
    agent: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    fresh_session: bool = False,
) -> list[str]:
    overrides = RoleCliOverrides(
        agent=agent, backend=backend, model=model, fresh_session=fresh_session
    )
    args = ["review", "base"]
    if request.scope.base_branch:
        args.append(request.scope.base_branch)
    if instructions:
        args.append(instructions)
    args += overrides.to_argv()
    return args


def _build_manual_review_task(
    config: VibeConfig,
    instructions: str | None,
    request: ReviewRequest,
    pr_number: int | None,
    log: Any,
) -> str | None:
    if instructions:
        log.info("Using custom task message")
        truncated = instructions[:60]
        suffix = "..." if len(instructions) > 60 else ""
        typer.echo(f"→ Custom task: {truncated}{suffix}")
        return instructions
    if config.review.review_prompt:
        log.info("Using configured task from vibe.toml")
        return config.review.review_prompt
    log.info("Using prompt file only (no custom task)")
    return request.task_guidance
