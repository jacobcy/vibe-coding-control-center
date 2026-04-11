"""Usecase layer for plan command orchestration (spec mode).

Issue-mode planning is now handled by roles/plan.py via run_issue_role_mode.
This module retains spec-mode logic until spec mode also migrates to the role
module pattern.
"""

import os
from pathlib import Path

from loguru import logger

from vibe3.agents.models import CodeagentResult, create_codeagent_command
from vibe3.agents.plan_prompt import make_plan_context_builder
from vibe3.agents.runner import CodeagentExecutionService
from vibe3.clients.github_client import GitHubClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.environment.worktree import WorktreeManager
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.coordinator import ExecutionCoordinator
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.plan import PlanRequest, PlanScope, PlanSpecInput
from vibe3.services.flow_service import FlowService
from vibe3.services.spec_ref_service import SpecRefService


class PlanUsecase:
    """Coordinate spec-mode plan command request building."""

    def __init__(
        self,
        config: VibeConfig | None = None,
        flow_service: FlowService | None = None,
        github_client: GitHubClient | None = None,
        spec_ref_service: SpecRefService | None = None,
        execution_service: CodeagentExecutionService | None = None,
        worktree_manager: WorktreeManager | None = None,
    ) -> None:
        self.config = config or VibeConfig.get_defaults()
        self.flow_service = flow_service or FlowService()
        self.github_client = github_client or GitHubClient()
        self.spec_ref_service = spec_ref_service or SpecRefService()
        self.execution_service = execution_service or CodeagentExecutionService(
            self.config
        )
        orchestra_config = OrchestraConfig.from_settings()
        self.worktree_manager = worktree_manager or WorktreeManager(
            config=orchestra_config, repo_path=Path.cwd()
        )

    def resolve_spec_plan(
        self,
        branch: str,
        file: Path | None = None,
        msg: str | None = None,
    ) -> PlanSpecInput:
        """Resolve spec planning input from file or inline message."""
        if file and msg:
            raise ValueError("Provide either --file or --msg, not both.")
        if not file and not msg:
            raise ValueError("Provide either --file or --msg.")

        if file:
            if not file.exists():
                raise FileNotFoundError(f"File not found: {file}")
            description = file.read_text(encoding="utf-8")
            spec_path = str(file.resolve())
        else:
            description = msg or ""
            spec_path = None

        request = PlanRequest(scope=PlanScope.for_spec(description))
        return PlanSpecInput(
            branch=branch,
            request=request,
            description=description,
            spec_path=spec_path,
        )

    def bind_spec(self, branch: str, spec_path: str) -> None:
        """Bind resolved spec path to current flow."""
        self.flow_service.bind_spec(branch, spec_path, "user")

    def execute_plan(
        self,
        request: PlanRequest,
        issue_number: int | None,
        branch: str,
        async_mode: bool = True,
        cli_args: list[str] | None = None,
    ) -> CodeagentResult:
        """Execute plan (spec mode) with codeagent backend."""
        log = logger.bind(
            domain="plan_usecase",
            action="execute_plan",
            issue=issue_number,
            branch=branch,
        )
        cwd = Path.cwd()
        if issue_number is not None:
            cwd = self.worktree_manager.acquire_issue_worktree(
                issue_number=issue_number,
                branch=branch,
            ).path

        command = create_codeagent_command(
            role="planner",
            context_builder=make_plan_context_builder(request, self.config),
            task=request.task_guidance,
            handoff_kind="plan",
            branch=branch,
            cwd=cwd,
            config=self.config,
        )
        if async_mode:
            if cli_args is None:
                raise ValueError("Async plan execution requires explicit cli_args")
            launch = ExecutionCoordinator(
                OrchestraConfig.from_settings(),
                SQLiteClient(),
            ).dispatch_execution(
                ExecutionRequest(
                    role="planner",
                    target_branch=branch,
                    target_id=issue_number or 0,
                    execution_name=(
                        f"vibe3-planner-issue-{issue_number}"
                        if issue_number is not None
                        else f"vibe3-planner-{branch.replace('/', '-')}"
                    ),
                    cmd=CodeagentExecutionService.build_self_invocation(cli_args),
                    cwd=str(cwd),
                    env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
                    refs=(
                        {"issue_number": str(issue_number)}
                        if issue_number is not None
                        else {}
                    ),
                    actor="agent:plan",
                    mode="async",
                )
            )
            return CodeagentResult(
                success=launch.launched,
                stderr=launch.reason or "",
                tmux_session=launch.tmux_session,
                log_path=Path(launch.log_path) if launch.log_path else None,
            )
        try:
            log.info("Executing plan agent")
            result = self.execution_service.execute_sync(command)
            if issue_number is not None:
                if result.success:
                    self._handle_plan_success(issue_number, branch)
                else:
                    self._handle_plan_failure(
                        Exception(result.stderr or "Plan execution failed"),
                        issue_number,
                    )
            log.info("Plan execution completed", success=result.success)
            return result
        except Exception as error:
            if issue_number is not None:
                self._handle_plan_failure(error, issue_number)
            raise

    def _handle_plan_success(
        self,
        issue_number: int,
        branch: str,
    ) -> None:
        """Handle plan execution success - publish PlanCompleted event."""
        from vibe3.domain.events import PlanCompleted
        from vibe3.domain.publisher import publish

        logger.bind(
            domain="plan_usecase",
            action="handle_plan_success",
            issue=issue_number,
        ).info("Publishing PlanCompleted event")
        publish(
            PlanCompleted(
                issue_number=issue_number,
                branch=branch,
                actor="agent:plan",
            )
        )

    def _handle_plan_failure(
        self,
        error: Exception,
        issue_number: int,
    ) -> None:
        """Handle plan execution failure - publish IssueFailed event."""
        from vibe3.domain.events import IssueFailed
        from vibe3.domain.publisher import publish

        logger.bind(
            domain="plan_usecase",
            action="handle_plan_failure",
            issue=issue_number,
        ).error("Plan execution failed", error=str(error))
        publish(
            IssueFailed(
                issue_number=issue_number,
                reason=str(error),
                actor="agent:plan",
            )
        )
