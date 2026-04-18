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
from vibe3.config.settings import VibeConfig
from vibe3.execution.codeagent_runner import CodeagentExecutionService
from vibe3.execution.codeagent_support import build_self_invocation
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
    build_required_ref_sync_spec,
    build_task_flow_branch_resolver,
    resolve_env_overridable_agent_options,
)
from vibe3.execution.role_contracts import REVIEWER_GATE_CONFIG
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.models.review import ReviewRequest, ReviewScope
from vibe3.models.snapshot import StructureDiff
from vibe3.roles.definitions import TriggerableRoleDefinition
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_recorder_unified import sanitize_handoff_content
from vibe3.services.handoff_service import HandoffService
from vibe3.services.issue_failure_service import (
    block_reviewer_noop_issue,
    fail_reviewer_issue,
)

REVIEWER_ROLE = TriggerableRoleDefinition(
    name="reviewer",
    registry_role="reviewer",
    gate_config=REVIEWER_GATE_CONFIG,
    trigger_name="review",
    trigger_state=IssueState.REVIEW,
    status_field="reviewer_status",
    # Dispatch: only prevent re-dispatch (audit_ref exists) or live session.
    # Business judgment is Manager's responsibility.
    dispatch_predicate=lambda fs, live: not fs.get("audit_ref") and not live,
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


def build_review_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    *,
    branch: str | None = None,
    repo_path: Path | None = None,
    report_ref: str | None = None,
    actor: str = "orchestra:reviewer",
) -> ExecutionRequest:
    """Build the reviewer async execution request for dispatch."""
    target_branch = branch or f"task/issue-{issue.number}"
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
        execution_name=f"vibe3-reviewer-issue-{issue.number}",
        refs=refs,
        worktree_requirement=REVIEWER_ROLE.gate_config.worktree,
        completion_gate=REVIEWER_ROLE.gate_config.completion_contract,
        repo_path=repo_path,
    )


def build_review_sync_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
) -> ExecutionRequest:
    """Build the reviewer sync execution request."""
    review_config = getattr(config, "review", None)
    review_prompt = review_config.review_prompt if review_config else None
    task = (
        review_prompt
        or f"Review implementation for issue #{issue.number}: {issue.title}"
    )

    return build_issue_sync_prompt_request(
        role="reviewer",
        issue=issue,
        target_branch=branch,
        prompt=task,
        options=options,
        task=task,
        actor=actor,
        execution_name=f"vibe3-reviewer-issue-{issue.number}",
        session_id=session_id,
        dry_run=dry_run,
        worktree_requirement=REVIEWER_ROLE.gate_config.worktree,
        completion_gate=REVIEWER_ROLE.gate_config.completion_contract,
    )


def publish_review_command_success(
    *,
    issue_number: int | None,
    branch: str | None,
    verdict: str,
) -> None:
    """Publish review completion lifecycle for manual review commands."""
    from vibe3.domain.events import ReviewCompleted
    from vibe3.domain.publisher import publish

    if issue_number is None or branch is None:
        return
    publish(
        ReviewCompleted(
            issue_number=issue_number,
            branch=branch,
            verdict=verdict,
            actor="agent:review",
        )
    )


def publish_review_command_failure(
    *,
    issue_number: int | None,
    reason: str,
) -> None:
    """Publish review failure lifecycle for manual review commands."""
    from vibe3.domain.events import IssueFailed
    from vibe3.domain.publisher import publish

    if issue_number is None:
        return
    publish(
        IssueFailed(
            issue_number=issue_number,
            reason=reason,
            actor="agent:review",
        )
    )


def _process_review_sync_result(
    *, issue_number: int, branch: str, actor: str, stdout: str
) -> None:
    """Process sync review output and write audit_ref to flow_state.

    This callback is invoked after sync execution completes but before
    the after snapshot is taken, allowing the review output to be parsed
    and audit_ref written before the required_ref gate check.
    """
    from vibe3.utils.constants import VERDICT_UNKNOWN

    # Parse verdict from stdout (fallback to UNKNOWN if parse fails)
    try:
        review = parse_codex_review(stdout)
        verdict = review.verdict
    except ReviewParserError:
        verdict = VERDICT_UNKNOWN

    # Create audit artifact and write audit_ref
    audit_ref = _resolve_authoritative_audit_ref(
        None,  # No handoff_file in sync mode
        stdout,
        verdict,
        branch,
    )
    _build_handoff_service(branch).record_audit(
        audit_ref=audit_ref,
        actor=actor,
        verdict=verdict,
    )


REVIEW_SYNC_SPEC = build_required_ref_sync_spec(
    role_name="reviewer",
    resolve_options=resolve_review_options,
    resolve_branch=REVIEW_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor: build_review_request(
        config,
        issue,
        actor=actor,
    ),
    build_sync_request=build_review_sync_request,
    required_ref="audit_ref",
    missing_reason="Reviewer completed without producing audit_ref",
    missing_ref_handler=block_reviewer_noop_issue,
    failure_handler=lambda issue_number, reason: fail_reviewer_issue(
        issue_number=issue_number,
        reason=reason,
    ),
    # No success_handler: state transitions are managed by the agent.
    # The no-op gate blocks if audit_ref exists but state unchanged.
    # Write audit_ref from stdout before snapshot.
    process_sync_result=_process_review_sync_result,
)


@dataclass
class ReviewRunResult:
    """Structured result for command-facing review output."""

    verdict: str
    handoff_file: str | None
    issue_number: int | None


class _BranchBoundGitClient(GitClient):
    """Git client shim that pins handoff writes to an explicit branch."""

    def __init__(self, branch: str) -> None:
        super().__init__()
        self._branch = branch

    def get_current_branch(self) -> str:
        return self._branch


def _build_handoff_service(branch: str | None) -> HandoffService:
    if not branch:
        return HandoffService()
    return HandoffService(git_client=_BranchBoundGitClient(branch))


def _create_minimal_audit_artifact(
    content: str,
    verdict: str,
    branch: str | None,
) -> Path:
    artifact_dir = _resolve_minimal_audit_dir(branch)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    branch_slug = (branch or "detached").replace("/", "-")
    artifact_path = artifact_dir / f"{branch_slug}-audit-auto-{timestamp}.md"
    sanitized_content = sanitize_handoff_content(content)
    artifact_path.write_text(
        "# Minimal Review Audit\n\n"
        f"VERDICT: {verdict}\n\n"
        "## Review Output\n\n"
        f"{sanitized_content.rstrip()}\n",
        encoding="utf-8",
    )
    return artifact_path


def _resolve_minimal_audit_dir(branch: str | None) -> Path:
    """Prefer a readable worktree-local docs/reports directory for audit output."""
    git = GitClient()
    worktree_root: Path | None = None

    if branch:
        worktree_root = git.find_worktree_path_for_branch(branch)

    if worktree_root is None:
        current_root = git.get_worktree_root()
        if current_root:
            worktree_root = Path(current_root)

    if worktree_root is not None:
        reports_dir = worktree_root / "docs" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir

    handoff_service = _build_handoff_service(branch)
    return handoff_service.ensure_handoff_dir()


def _resolve_authoritative_audit_ref(
    handoff_file: str | None,
    review_output: str,
    verdict: str,
    branch: str | None,
) -> str:
    if handoff_file:
        handoff_path = Path(handoff_file)
        if handoff_path.exists():
            return str(handoff_path)
    return str(_create_minimal_audit_artifact(review_output, verdict, branch))


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
    issue_number = linked_issues[0] if linked_issues else None
    head_branch = pr_data.head_branch if pr_data else None
    request = ReviewRequest(
        scope=ReviewScope.for_pr(pr_number),
        changed_symbols=changed_symbols(inspect_runner(["pr", str(pr_number)])),
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
) -> tuple[ReviewRequest, int | None]:
    """Build request payload for base-branch review."""
    service = flow_service or FlowService()
    flow = service.get_flow_status(current_branch)
    issue_number = flow.task_issue_number if flow else None
    raw_diff = snapshot_diff_builder(base_branch, current_branch)
    structure_diff = (
        cast(StructureDiff | None, raw_diff) if raw_diff is not None else None
    )
    request = ReviewRequest(
        scope=ReviewScope.for_base(base_branch),
        changed_symbols=changed_symbols(inspect_runner(["base", base_branch])),
        structure_diff=structure_diff,
    )
    return request, issue_number


def execute_manual_review(
    *,
    request: ReviewRequest,
    dry_run: bool,
    instructions: str | None,
    issue_number: int | None = None,
    pr_number: int | None = None,
    branch: str | None = None,
    async_mode: bool = True,
    config: VibeConfig | None = None,
    flow_service: FlowService | None = None,
    review_parser: Callable[[str], ParsedReview] = parse_codex_review,
    context_builder: Callable[..., object] = make_review_context_builder,
) -> ReviewRunResult:
    """Execute manual review for `review pr` and `review base`."""
    cfg = config or VibeConfig.get_defaults()
    service = flow_service or FlowService()
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
    )
    if async_mode and not dry_run and branch:
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

    result = CodeagentExecutionService(cfg).execute_sync(command)
    if dry_run:
        return ReviewRunResult("DRY_RUN", None, issue_number)

    # 增加容错性：即使 parser 失败也写入 audit_ref
    from vibe3.utils.constants import VERDICT_UNKNOWN

    try:
        review = review_parser(result.stdout)
        verdict = review.verdict
    except ReviewParserError as err:
        # Parser 失败时，verdict 为空，交给 manager 判断
        logger.bind(domain="review").warning(
            f"Failed to parse review output, using verdict=UNKNOWN: {err}"
        )
        verdict = VERDICT_UNKNOWN

    # 无论 parser 是否成功，只要有输出就写入 audit_ref
    audit_ref = _resolve_authoritative_audit_ref(
        str(result.handoff_file) if result.handoff_file else None,
        result.stdout,  # ← 直接使用原始输出
        verdict,
        branch,
    )

    flow = service.get_flow_status(branch) if branch else None
    if flow is not None and branch is not None:
        _build_handoff_service(branch).record_audit(
            audit_ref=audit_ref,
            actor="agent:review",
            verdict=verdict,
        )
        publish_review_command_success(
            issue_number=issue_number,
            branch=branch,
            verdict=verdict,  # ← 使用实际或 UNKNOWN verdict
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
        OrchestraConfig.from_settings(),
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
