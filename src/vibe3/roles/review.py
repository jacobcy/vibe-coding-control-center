"""Reviewer role definition and request builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, cast

import typer
from loguru import logger

from vibe3.agents import (
    build_review_prompt_body,
    build_snapshot_diff,
    create_codeagent_command,
    describe_review_sections,
    make_review_context_builder,
    run_inspect_json,
)
from vibe3.analysis.inspect_output_adapter import changed_symbols
from vibe3.config.loader import load_runtime_config
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.config.role_gates import REVIEWER_GATE_CONFIG
from vibe3.config.settings import VibeConfig
from vibe3.execution.codeagent_runner import CodeagentExecutionService
from vibe3.execution.codeagent_support import build_self_invocation
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
    build_issue_sync_spec,
    build_task_flow_branch_resolver,
    resolve_env_overridable_agent_options,
)
from vibe3.execution.prompt_meta import build_prompt_meta
from vibe3.models import IssueInfo, IssueState
from vibe3.models.execution_request import ExecutionRequest
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.review import ReviewRequest, ReviewScope
from vibe3.models.snapshot import StructureDiff
from vibe3.models.worktree import WorktreeRequirement
from vibe3.roles.definitions import RoleOutputContract, TriggerableRoleDefinition
from vibe3.roles.review_helpers import (
    ReviewRunResult,
    finalize_review_output,
)
from vibe3.services.convention_resolver import ConventionResolver
from vibe3.services.error_helpers import record_dispatch_failure_if_unexpected
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_failure_service import fail_reviewer_issue


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
            f"No issue linked to flow '{branch}'.\n"
            "Run 'vibe3 flow bind <issue>' first."
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


def resolve_review_options(config: OrchestraConfig) -> Any:
    """Resolve reviewer agent options with env override support."""
    from vibe3.models.review_runner import AgentOptions

    runtime_config = load_runtime_config()
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
    resolver = ConventionResolver.from_repo()
    convention = resolver.resolve()
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
    command_args = ["review", "--branch", target_branch, "--no-async"]

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
    from vibe3.clients.sqlite_client import SQLiteClient

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


REVIEW_SYNC_SPEC = build_issue_sync_spec(
    role_name="reviewer",
    resolve_options=resolve_review_options,
    resolve_branch=REVIEW_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor: build_issue_review_request(
        issue,
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
    inspect_args: list[str],
    structure_diff: StructureDiff | None = None,
    inspect_runner: Callable[[list[str]], dict[str, object]] = run_inspect_json,
) -> tuple[ReviewRequest, int | None, str | None]:
    """Consolidated factory for manual review request payloads (PR and Base)."""
    request = ReviewRequest(
        scope=scope,
        changed_symbols=changed_symbols(inspect_runner(inspect_args)),
        structure_diff=structure_diff,
    )
    return request, issue_number, head_branch


def build_base_review_request(
    current_branch: str,
    base_branch: str,
    *,
    flow_service: FlowService | None = None,
    inspect_runner: Callable[[list[str]], dict[str, object]] = run_inspect_json,
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
        inspect_args=["base", base_branch],
        structure_diff=(
            cast(StructureDiff | None, raw_diff) if raw_diff is not None else None
        ),
        inspect_runner=inspect_runner,
    )


def execute_manual_review_async(
    *,
    request: ReviewRequest,
    instructions: str | None,
    issue_number: int | None = None,
    pr_number: int | None = None,
    branch: str,
) -> ReviewRunResult:
    """Execute manual review in async mode (tmux wrapper)."""
    launch = _dispatch_async_manual_review(
        request=request,
        branch=branch,
        issue_number=issue_number,
        pr_number=pr_number,
        instructions=instructions,
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
        return ReviewRunResult("ERROR", None, issue_number)
    return ReviewRunResult("ASYNC", None, issue_number)


def execute_manual_review_sync(
    *,
    request: ReviewRequest,
    dry_run: bool,
    instructions: str | None,
    issue_number: int | None = None,
    pr_number: int | None = None,
    branch: str | None = None,
    config: VibeConfig | None = None,
    flow_service: FlowService | None = None,
    context_builder: Callable[..., object] = make_review_context_builder,
    show_prompt: bool = False,
) -> ReviewRunResult:
    """Execute manual review in sync mode (direct execution)."""
    _ = flow_service
    cfg = config or VibeConfig.get_defaults()
    log = logger.bind(domain="review", scope=request.scope.kind)
    task = _build_manual_review_task(cfg, instructions, request, pr_number, log)
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
) -> Any:
    cli_args = _build_manual_review_async_cli_args(request, instructions)
    target_id = pr_number or issue_number or 0
    execution_name = (
        f"vibe3-reviewer-issue-{target_id}"
        if issue_number is not None
        else f"vibe3-reviewer-{request.scope.kind}-{target_id or 'adhoc'}"
    )
    from vibe3.clients.sqlite_client import SQLiteClient
    from vibe3.execution.issue_role_support import resolve_orchestra_repo_root

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
) -> list[str]:
    args = ["review", "base"]
    if request.scope.base_branch:
        args.append(request.scope.base_branch)
    if instructions:
        args.append(instructions)
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
