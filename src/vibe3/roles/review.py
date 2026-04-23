"""Reviewer role definition and request builders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, cast

import typer
from loguru import logger

from vibe3.agents.models import create_codeagent_command
from vibe3.agents.review_parser import (
    ParsedReview,
    ReviewParserError,
    parse_codex_review,
)
from vibe3.agents.review_pipeline_helpers import build_snapshot_diff, run_inspect_json
from vibe3.agents.review_prompt import make_review_context_builder
from vibe3.analysis.inspect_output_adapter import changed_symbols
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.orchestra_settings import load_orchestra_config
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
from vibe3.execution.role_contracts import REVIEWER_GATE_CONFIG
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.review import ReviewRequest, ReviewScope
from vibe3.models.snapshot import StructureDiff
from vibe3.roles.definitions import TriggerableRoleDefinition
from vibe3.services.artifact_parser import ArtifactParser
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_service import HandoffService
from vibe3.services.issue_failure_service import fail_reviewer_issue
from vibe3.utils.path_helpers import BranchBoundGitClient

REVIEWER_ROLE = TriggerableRoleDefinition(
    name="reviewer",
    registry_role="reviewer",
    worktree=REVIEWER_GATE_CONFIG,
    trigger_name="review",
    trigger_state=IssueState.REVIEW,
)


def resolve_review_options(config: OrchestraConfig) -> Any:
    """Resolve reviewer agent options with env override support."""
    from vibe3.execution.agent_resolver import resolve_reviewer_agent_options

    return resolve_env_overridable_agent_options(
        backend_env_key="VIBE3_REVIEWER_BACKEND",
        model_env_key="VIBE3_REVIEWER_MODEL",
        fallback_resolver=lambda: resolve_reviewer_agent_options(
            config, VibeConfig.get_defaults()
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
) -> ExecutionRequest:
    """Consolidated factory for issue review requests (async and sync)."""
    target_branch = branch or f"task/issue-{issue.number}"
    execution_name = f"vibe3-reviewer-issue-{issue.number}"

    if sync:
        cfg = config or load_orchestra_config()
        review_config = getattr(cfg, "review", None)
        review_prompt = review_config.review_prompt if review_config else None
        task = (
            review_prompt
            or f"Review implementation for issue #{issue.number}: {issue.title}"
        )

        return build_issue_sync_prompt_request(
            role="reviewer",
            issue=issue,
            target_branch=target_branch,
            prompt=task,
            options=options,
            task=task,
            actor=actor,
            execution_name=execution_name,
            session_id=session_id,
            dry_run=dry_run,
            worktree_requirement=REVIEWER_ROLE.worktree,
        )

    refs: dict[str, str] = {"issue_number": str(issue.number)}
    if report_ref:
        refs["report_ref"] = report_ref
    command_args = ["review", "--issue", str(issue.number), "--no-async"]
    if report_ref:
        command_args.extend(["--report-ref", report_ref])

    return build_issue_async_cli_request(
        role="reviewer",
        issue=issue,
        target_branch=target_branch,
        command_args=command_args,
        actor=actor,
        execution_name=execution_name,
        refs=refs,
        worktree_requirement=REVIEWER_ROLE.worktree,
        repo_path=repo_path,
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
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
) -> ExecutionRequest:
    return build_issue_review_request(
        issue,
        branch=branch,
        session_id=session_id,
        options=options,
        actor=actor,
        dry_run=dry_run,
        sync=True,
        config=config,
    )


def _process_review_sync_result(
    *, issue_number: int, branch: str, actor: str, stdout: str
) -> None:
    """Process sync review output and write audit_ref to flow_state."""
    finalize_review_output(
        review_output=stdout,
        branch=branch,
        actor=actor,
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


@dataclass
class ReviewRunResult:
    """Structured result for command-facing review output."""

    verdict: str
    handoff_file: str | None
    issue_number: int | None


def _create_minimal_audit_artifact(
    content: str,
    verdict: str,
    branch: str | None,
) -> Path:
    artifact_dir = _resolve_minimal_audit_dir(branch)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    branch_slug = (branch or "detached").replace("/", "-")
    artifact_path = artifact_dir / f"{branch_slug}-audit-auto-{timestamp}.md"
    sanitized_content = ArtifactParser.sanitize_handoff_content(content)
    artifact_path.write_text(
        "# Minimal Review Audit\n\n"
        f"VERDICT: {verdict}\n\n"
        "## Review Output\n\n"
        f"{sanitized_content.rstrip()}\n",
        encoding="utf-8",
    )
    return artifact_path


def _resolve_minimal_audit_dir(branch: str | None) -> Path:
    git = GitClient()
    worktree_root: Path | None = None

    try:
        current_root = git.get_worktree_root()
        if current_root:
            worktree_root = Path(current_root)
    except Exception:
        pass

    if worktree_root is None and branch:
        try:
            worktree_root = git.find_worktree_path_for_branch(branch)
        except Exception:
            pass

    if worktree_root is not None:
        reports_dir = worktree_root / "docs" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir

    reports_dir = Path.cwd() / "docs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def _load_existing_audit_ref(branch: str | None) -> str | None:
    if not branch:
        return None
    flow = FlowService().get_flow_status(branch)
    if flow and flow.audit_ref:
        return flow.audit_ref
    return None


def _resolve_review_verdict(
    review_output: str,
    *,
    audit_ref: str | None = None,
) -> str:
    from vibe3.utils.constants import VERDICT_UNKNOWN

    try:
        review = parse_codex_review(review_output)
        return review.verdict
    except ReviewParserError:
        pass

    if audit_ref:
        audit_path = Path(audit_ref)
        if audit_path.exists():
            try:
                review = parse_codex_review(audit_path.read_text(encoding="utf-8"))
                return review.verdict
            except (OSError, ReviewParserError):
                pass

    return VERDICT_UNKNOWN


def finalize_review_output(
    *,
    review_output: str,
    branch: str | None,
    actor: str,
) -> tuple[str, str]:
    """Finalize review output by confirming audit_ref and writing verdict."""
    existing_audit_ref = _load_existing_audit_ref(branch)
    reviewer_wrote_audit = bool(existing_audit_ref)

    audit_ref: str
    if reviewer_wrote_audit:
        audit_ref = existing_audit_ref  # type: ignore[assignment]
    else:
        audit_ref = str(
            _create_minimal_audit_artifact(
                review_output,
                _resolve_review_verdict(review_output),
                branch,
            )
        )

    if reviewer_wrote_audit:
        audit_path = Path(audit_ref)
        audit_content = None
        if audit_path.exists():
            try:
                audit_content = audit_path.read_text(encoding="utf-8")
            except OSError:
                pass
        verdict = _resolve_review_verdict(
            audit_content or review_output,
            audit_ref=audit_ref,
        )
    else:
        verdict = _resolve_review_verdict(review_output, audit_ref=audit_ref)

    try:
        handoff_svc = (
            HandoffService(git_client=BranchBoundGitClient(branch))
            if branch
            else HandoffService()
        )
        handoff_svc.record_audit(
            audit_ref=audit_ref,
            actor=actor,
            verdict=verdict,  # type: ignore[arg-type]
            is_system_auto=not reviewer_wrote_audit,
        )
    except Exception as exc:
        logger.bind(domain="review", action="finalize").warning(
            f"Failed to record audit handoff: {exc}"
        )

    return audit_ref, verdict


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


def build_pr_review_request(
    pr_number: int,
    *,
    github_client: GitHubClient | None = None,
    inspect_runner: Callable[[list[str]], dict[str, object]] = run_inspect_json,
) -> tuple[ReviewRequest, int | None, str | None]:
    """Build request payload for PR review."""
    client = github_client or GitHubClient()
    pr_data = client.get_pr(pr_number)
    linked_issues = parse_linked_issues(pr_data.body) if pr_data else []
    return build_manual_review_request_payload(
        scope=ReviewScope.for_pr(pr_number),
        issue_number=linked_issues[0] if linked_issues else None,
        head_branch=pr_data.head_branch if pr_data else None,
        inspect_args=["pr", str(pr_number)],
        inspect_runner=inspect_runner,
    )


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
    if not launch.launched:
        logger.bind(domain="review").warning(
            "Async review launch skipped",
            reason=launch.reason,
            reason_code=launch.reason_code,
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
    review_parser: Callable[[str], ParsedReview] = parse_codex_review,
    context_builder: Callable[..., object] = make_review_context_builder,
) -> ReviewRunResult:
    """Execute manual review in sync mode (direct execution)."""
    _ = flow_service, review_parser
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
        pre_gate_callback=_process_review_sync_result,
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
            cwd=str(Path.cwd()),
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
    if request.scope.kind == "pr":
        args = ["review", "pr", str(request.scope.pr_number)]
    else:
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
    if pr_number:
        if instructions:
            task = f"审查 PR #{pr_number}: {instructions}"
        elif config.review.review_prompt:
            task = f"审查 PR #{pr_number}: {config.review.review_prompt}"
        else:
            task = f"审查 PR #{pr_number} 的变更"
        log.info("Using PR-specific task")
        typer.echo(f"→ Task: {task}")
        return task
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
