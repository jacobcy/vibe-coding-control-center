"""Usecase layer for review command orchestration."""

from dataclasses import dataclass
from typing import Any, Callable, cast

import typer
from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.clients.github_issues_ops import parse_linked_issues
from vibe3.config.settings import VibeConfig
from vibe3.models.orchestration import IssueState
from vibe3.models.review import ReviewRequest, ReviewScope
from vibe3.models.snapshot import StructureDiff
from vibe3.services.codeagent_execution_service import (
    CodeagentExecutionService,
    create_codeagent_command,
)
from vibe3.services.context_builder import make_review_context_builder
from vibe3.services.flow_service import FlowService
from vibe3.services.inspect_output_adapter import changed_symbols
from vibe3.services.label_service import LabelService
from vibe3.services.review_parser import ParsedReview, parse_codex_review
from vibe3.services.review_pipeline_helpers import build_snapshot_diff, run_inspect_json


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
        execution_service_factory: Callable[[VibeConfig], Any] = (
            CodeagentExecutionService
        ),
        command_builder: Callable[..., object] = create_codeagent_command,
    ) -> None:
        self.config = config or VibeConfig.get_defaults()
        self.flow_service = flow_service or FlowService()
        self.github_client = github_client or GitHubClient()
        self.inspect_runner = inspect_runner
        self.snapshot_diff_builder = snapshot_diff_builder
        self.review_parser = review_parser
        self.context_builder = context_builder
        self.execution_service_factory = execution_service_factory
        self.command_builder = command_builder

    def build_pr_review(self, pr_number: int) -> tuple[ReviewRequest, int | None]:
        """Build request payload for PR review."""
        pr_data = self.github_client.get_pr(pr_number)
        linked_issues = parse_linked_issues(pr_data.body) if pr_data else []
        issue_number = linked_issues[0] if linked_issues else None
        request = ReviewRequest(
            scope=ReviewScope.for_pr(pr_number),
            changed_symbols=self._load_changed_symbols(["pr", str(pr_number)]),
        )
        return request, issue_number

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
        async_mode: bool = False,
        worktree: bool = False,
    ) -> ReviewRunResult:
        """Execute review request and return a command-facing summary."""
        log = logger.bind(domain="review", scope=request.scope.kind)
        task = self._build_task(instructions, request, pr_number, log)
        exec_svc = self.execution_service_factory(self.config)
        command = self.command_builder(
            role="reviewer",
            context_builder=self.context_builder(request, self.config),
            task=task,
            dry_run=dry_run,
            handoff_kind="review",
            handoff_metadata={},
            config=self.config,
            branch=branch,
            worktree=worktree,
        )
        if async_mode and not dry_run and branch:
            exec_svc.execute(command, async_mode=True)
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

        review = self.review_parser(result.stdout)
        self._transition_issue(issue_number)
        return ReviewRunResult(
            verdict=review.verdict,
            handoff_file=str(result.handoff_file) if result.handoff_file else None,
            issue_number=issue_number,
        )

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

    @staticmethod
    def _transition_issue(issue_number: int | None) -> None:
        """Move linked issue into review state when possible."""
        if issue_number is None:
            return
        label_result = LabelService().confirm_issue_state(
            issue_number,
            to_state=IssueState.REVIEW,
            actor="agent:review",
        )
        if label_result == "blocked":
            typer.echo(
                "Warning: Failed to transition issue state: state_transition_blocked",
                err=True,
            )

    def _load_changed_symbols(
        self, inspect_args: list[str]
    ) -> dict[str, list[str]] | None:
        """Load changed_symbols from inspect output with stable casting."""
        inspect_data = self.inspect_runner(inspect_args)
        return changed_symbols(inspect_data)
