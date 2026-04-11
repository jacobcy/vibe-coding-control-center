"""Usecase layer for PR and base review command modes.

Issue-based review is handled by roles/review.py + issue_role_sync_runner.
This module serves the manual CLI modes: `review pr` and `review base`.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, cast

import typer
from loguru import logger

from vibe3.agents.review_parser import (
    ParsedReview,
    ReviewParserError,
    parse_codex_review,
)
from vibe3.agents.review_pipeline_helpers import build_snapshot_diff, run_inspect_json
from vibe3.agents.review_prompt import make_review_context_builder
from vibe3.agents.runner import (
    CodeagentExecutionService,
    create_codeagent_command,
)
from vibe3.analysis.inspect_output_adapter import changed_symbols
from vibe3.clients.git_client import GitClient
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.review import ReviewRequest, ReviewScope
from vibe3.models.snapshot import StructureDiff
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_recorder_unified import sanitize_handoff_content
from vibe3.services.handoff_service import HandoffService


class _BranchBoundGitClient(GitClient):
    """Git client shim that pins handoff writes to an explicit branch."""

    def __init__(self, branch: str) -> None:
        super().__init__()
        self._branch = branch

    def get_current_branch(self) -> str:
        return self._branch


def _build_handoff_service(branch: str | None) -> HandoffService:
    """Build handoff service pinned to the target branch when provided."""
    if not branch:
        return HandoffService()

    return HandoffService(git_client=_BranchBoundGitClient(branch))


def _create_minimal_audit_artifact(
    content: str,
    verdict: str,
    branch: str | None,
) -> Path:
    """Create a minimal canonical audit artifact from parsed review output."""
    handoff_service = _build_handoff_service(branch)
    handoff_dir = handoff_service.ensure_handoff_dir()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifact_path = handoff_dir / f"audit-auto-{timestamp}.md"
    sanitized_content = sanitize_handoff_content(content)
    artifact_path.write_text(
        "# Minimal Review Audit\n\n"
        f"VERDICT: {verdict}\n\n"
        "## Review Output\n\n"
        f"{sanitized_content.rstrip()}\n",
        encoding="utf-8",
    )
    return artifact_path


def _resolve_authoritative_audit_ref(
    handoff_file: str | None,
    review_output: str,
    verdict: str,
    branch: str | None,
) -> str:
    """Resolve the authoritative audit ref for a successful review."""
    if handoff_file:
        handoff_path = Path(handoff_file)
        if handoff_path.exists():
            return str(handoff_path)

    return str(_create_minimal_audit_artifact(review_output, verdict, branch))


def _resolve_error_audit_ref(
    handoff_file: str | None,
    review_output: str,
    branch: str | None,
) -> str:
    """Resolve a stable audit path for parse-error diagnostics."""
    if handoff_file:
        handoff_path = Path(handoff_file)
        if handoff_path.exists():
            return str(handoff_path)

    return str(_create_minimal_audit_artifact(review_output, "ERROR", branch))


@dataclass
class ReviewRunResult:
    """Structured result for command-facing review output."""

    verdict: str
    handoff_file: str | None
    issue_number: int | None


class ReviewUsecase:
    """Coordinate review command request building and execution."""

    def __init__(
        self,
        config: VibeConfig | None = None,
        flow_service: FlowService | None = None,
        github_client: GitHubClient | None = None,
        inspect_runner: Callable[[list[str]], dict[str, object]] = run_inspect_json,
        snapshot_diff_builder: Callable[[str, str | None], object | None] = (
            build_snapshot_diff
        ),
        review_parser: Callable[[str], ParsedReview] = parse_codex_review,
        context_builder: Callable[..., object] = make_review_context_builder,
    ) -> None:
        self.config = config or VibeConfig.get_defaults()
        self.flow_service = flow_service or FlowService()
        self.github_client = github_client or GitHubClient()
        self.inspect_runner = inspect_runner
        self.snapshot_diff_builder = snapshot_diff_builder
        self.review_parser = review_parser
        self.context_builder = context_builder

    def build_pr_review(
        self, pr_number: int
    ) -> tuple[ReviewRequest, int | None, str | None]:
        """Build request payload for PR review."""
        pr_data = self.github_client.get_pr(pr_number)
        linked_issues = parse_linked_issues(pr_data.body) if pr_data else []
        issue_number = linked_issues[0] if linked_issues else None
        head_branch = pr_data.head_branch if pr_data else None
        request = ReviewRequest(
            scope=ReviewScope.for_pr(pr_number),
            changed_symbols=self._load_changed_symbols(["pr", str(pr_number)]),
        )
        return request, issue_number, head_branch

    def build_base_review(
        self,
        current_branch: str,
        base_branch: str,
    ) -> tuple[ReviewRequest, int | None]:
        """Build request payload for base-branch review."""
        flow = self.flow_service.get_flow_status(current_branch)
        issue_number = flow.task_issue_number if flow else None
        raw_diff = self.snapshot_diff_builder(base_branch, current_branch)
        structure_diff = (
            cast(StructureDiff | None, raw_diff) if raw_diff is not None else None
        )
        request = ReviewRequest(
            scope=ReviewScope.for_base(base_branch),
            changed_symbols=self._load_changed_symbols(["base", base_branch]),
            structure_diff=structure_diff,
        )
        return request, issue_number

    def execute_review(
        self,
        request: ReviewRequest,
        dry_run: bool,
        instructions: str | None,
        issue_number: int | None = None,
        pr_number: int | None = None,
        branch: str | None = None,
        async_mode: bool = True,
    ) -> ReviewRunResult:
        """Execute review request and return a command-facing summary."""
        from vibe3.domain.events import IssueFailed, ReviewCompleted
        from vibe3.domain.publisher import publish

        log = logger.bind(domain="review", scope=request.scope.kind)
        task = self._build_task(instructions, request, pr_number, log)
        exec_svc = CodeagentExecutionService(self.config)
        command = create_codeagent_command(
            role="reviewer",
            context_builder=cast(
                Callable[[], str], self.context_builder(request, self.config)
            ),
            task=task,
            dry_run=dry_run,
            handoff_kind="review",
            handoff_metadata={},
            config=self.config,
            branch=branch,
        )
        if async_mode and not dry_run and branch:
            launch = self._dispatch_async_review(
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
                return ReviewRunResult(
                    verdict="ERROR",
                    handoff_file=None,
                    issue_number=issue_number,
                )
            return ReviewRunResult(
                verdict="ASYNC",
                handoff_file=None,
                issue_number=issue_number,
            )

        result = exec_svc.execute_sync(command)
        if dry_run:
            return ReviewRunResult(
                verdict="DRY_RUN",
                handoff_file=None,
                issue_number=issue_number,
            )

        try:
            review = self.review_parser(result.stdout)
            audit_ref = _resolve_authoritative_audit_ref(
                str(result.handoff_file) if result.handoff_file else None,
                result.stdout,
                review.verdict,
                branch,
            )
            flow = self.flow_service.get_flow_status(branch) if branch else None
            if flow is not None and branch is not None:
                _build_handoff_service(branch).record_audit(
                    audit_ref=audit_ref,
                    actor="agent:review",
                )
                # Publish ReviewCompleted event (only if issue_number is set)
                if issue_number is not None:
                    review_event = ReviewCompleted(
                        issue_number=issue_number,
                        branch=branch,
                        verdict=review.verdict,
                        actor="agent:review",
                    )
                    publish(review_event)
            return ReviewRunResult(
                verdict=review.verdict,
                handoff_file=audit_ref,
                issue_number=issue_number,
            )
        except ReviewParserError as err:
            logger.bind(domain="review").error(f"Failed to parse review output: {err}")
            error_audit_ref = _resolve_error_audit_ref(
                str(result.handoff_file) if result.handoff_file else None,
                result.stdout,
                branch,
            )
            flow = self.flow_service.get_flow_status(branch) if branch else None
            if flow is not None and branch is not None:
                _build_handoff_service(branch).record_audit(
                    audit_ref=error_audit_ref,
                    actor="agent:review",
                )
            # Publish IssueFailed event
            if issue_number is not None:
                event = IssueFailed(
                    issue_number=issue_number,
                    reason=f"review parse failed: {err}",
                    actor="agent:review",
                )
                publish(event)
            return ReviewRunResult(
                verdict="ERROR",
                handoff_file=error_audit_ref,
                issue_number=issue_number,
            )

    def _dispatch_async_review(
        self,
        *,
        request: ReviewRequest,
        branch: str,
        issue_number: int | None,
        pr_number: int | None,
        instructions: str | None,
    ) -> Any:
        """Launch async review through the unified execution coordinator."""
        cli_args = self._build_async_cli_args(request, instructions)
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
                cmd=CodeagentExecutionService.build_self_invocation(cli_args),
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

    @staticmethod
    def _build_async_cli_args(
        request: ReviewRequest,
        instructions: str | None,
    ) -> list[str]:
        """Build explicit self-invocation args for async review."""
        if request.scope.kind == "pr":
            args = ["review", "pr", str(request.scope.pr_number)]
        else:
            args = ["review", "base"]
            if request.scope.base_branch:
                args.append(request.scope.base_branch)
        if instructions:
            args.append(instructions)
        return args

    def _build_task(
        self,
        instructions: str | None,
        request: ReviewRequest,
        pr_number: int | None,
        log: Any,
    ) -> str | None:
        """Build task text used by the codeagent wrapper."""
        if pr_number:
            if instructions:
                task = f"审查 PR #{pr_number}: {instructions}"
            elif self.config.review.review_prompt:
                task = f"审查 PR #{pr_number}: {self.config.review.review_prompt}"
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
        if self.config.review.review_prompt:
            log.info("Using configured task from vibe.toml")
            return self.config.review.review_prompt
        log.info("Using prompt file only (no custom task)")
        return request.task_guidance

    def _load_changed_symbols(
        self, inspect_args: list[str]
    ) -> dict[str, list[str]] | None:
        """Load changed_symbols from inspect output with stable casting."""
        inspect_data = self.inspect_runner(inspect_args)
        return changed_symbols(inspect_data)
