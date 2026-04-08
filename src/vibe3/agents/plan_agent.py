"""Usecase layer for plan command orchestration.

Migrated from vibe3.services.plan_usecase.
"""

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from vibe3.agents.models import AgentSpec, CodeagentResult
from vibe3.agents.plan_prompt import make_plan_context_builder
from vibe3.agents.runner import CodeagentExecutionService
from vibe3.clients.github_client import GitHubClient
from vibe3.config.settings import VibeConfig
from vibe3.environment.session import SessionManager
from vibe3.environment.worktree import WorktreeManager
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.plan import PlanRequest, PlanScope
from vibe3.orchestra.config import OrchestraConfig
from vibe3.services.authoritative_ref_gate import require_authoritative_ref
from vibe3.services.flow_service import FlowService
from vibe3.services.issue_failure_service import (
    block_planner_noop_issue,
    confirm_plan_handoff,
    fail_planner_issue,
)
from vibe3.services.spec_ref_service import SpecRefService


@dataclass
class PlanTaskInput:
    """Resolved inputs for task planning."""

    issue_number: int
    branch: str
    request: PlanRequest
    used_flow_issue: bool = False


@dataclass
class PlanSpecInput:
    """Resolved inputs for spec planning."""

    branch: str
    request: PlanRequest
    description: str
    spec_path: str | None = None


class PlanUsecase:
    """Coordinate plan command request building with reusable services."""

    def __init__(
        self,
        config: VibeConfig | None = None,
        flow_service: FlowService | None = None,
        github_client: GitHubClient | None = None,
        spec_ref_service: SpecRefService | None = None,
        execution_service: CodeagentExecutionService | None = None,
        session_manager: SessionManager | None = None,
        worktree_manager: WorktreeManager | None = None,
    ) -> None:
        self.config = config or VibeConfig.get_defaults()
        self.flow_service = flow_service or FlowService()
        self.github_client = github_client or GitHubClient()
        self.spec_ref_service = spec_ref_service or SpecRefService()
        self.execution_service = execution_service or CodeagentExecutionService(
            self.config
        )
        self.session_manager = session_manager or SessionManager(repo_path=Path.cwd())
        # WorktreeManager 需要 OrchestraConfig，从 VibeConfig 转换
        orchestra_config = OrchestraConfig.from_settings()
        self.worktree_manager = worktree_manager or WorktreeManager(
            config=orchestra_config, repo_path=Path.cwd()
        )

    def resolve_task_plan(
        self,
        branch: str,
        issue_number: int | None = None,
    ) -> PlanTaskInput:
        """Resolve task planning input from explicit issue or current flow."""
        used_flow_issue = False
        if issue_number is None:
            flow = self.flow_service.get_flow_status(branch)
            if not flow or not flow.task_issue_number:
                raise ValueError(
                    "No issue number provided and current flow has no task issue.\n"
                    "Use 'vibe3 plan --issue <issue>' or bind a task to the "
                    "current flow."
                )
            issue_number = flow.task_issue_number
            used_flow_issue = True

        flow = self.flow_service.get_flow_status(branch)
        guidance = self._build_flow_plan_guidance(flow, issue_number) if flow else None
        request = PlanRequest(
            scope=PlanScope.for_task(issue_number),
            task_guidance=guidance,
        )
        return PlanTaskInput(
            issue_number=issue_number,
            branch=branch,
            request=request,
            used_flow_issue=used_flow_issue,
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

    def _build_issue_context(self, issue_number: int, heading: str) -> str | None:
        try:
            issue = self.github_client.view_issue(issue_number)
        except (FileNotFoundError, RuntimeError):
            return None
        if not isinstance(issue, dict):
            return None
        parts = [f"## {heading}", f"Issue: #{issue_number}"]
        title = issue.get("title")
        body = issue.get("body")
        if title:
            parts.append(f"Title: {title}")
        if body:
            parts.extend(["", body])
        return "\n".join(parts)

    def _build_flow_plan_guidance(
        self,
        flow: FlowStatusResponse | None,
        issue_number: int,
    ) -> str | None:
        sections: list[str] = []
        task_context = self._build_issue_context(issue_number, "Task Issue Context")
        if task_context:
            sections.append(task_context)

        spec_ref = getattr(flow, "spec_ref", None)
        if spec_ref:
            spec_info = self.spec_ref_service.parse_spec_ref(spec_ref)
            spec_content = self.spec_ref_service.get_spec_content_for_prompt(spec_info)
            if spec_info.display and spec_info.display != spec_ref:
                sections.append(f"## Spec Reference\nSpec Ref: {spec_info.display}")
            if spec_content:
                sections.append(f"## Spec Context\n{spec_content}")

        return "\n\n".join(sections) if sections else None

    def execute_plan(
        self,
        request: PlanRequest,
        issue_number: int,
        branch: str,
        async_mode: bool = True,
    ) -> CodeagentResult:
        """执行 plan 的完整流程。

        职责：
        1. 获取资源（session、worktree）
        2. 构建 AgentSpec（包含回调）
        3. 执行 Agent
        4. 清理资源（finally）

        Args:
            request: Plan 请求数据
            issue_number: GitHub issue 编号
            branch: Git 分支名
            async_mode: 是否异步执行

        Returns:
            执行结果

        Raises:
            Exception: 执行过程中的异常
        """
        log = logger.bind(
            domain="plan_usecase",
            action="execute_plan",
            issue=issue_number,
            branch=branch,
        )

        # 1. 获取资源
        log.info("Acquiring resources")
        self.session_manager.create_codeagent_session(
            sync_mode=not async_mode,
            prefix="plan",
        )
        worktree = self.worktree_manager.acquire_issue_worktree(
            issue_number=issue_number,
            branch=branch,
        )

        # 2. 构建 AgentSpec
        spec = self.create_plan_spec(request, issue_number, branch)

        # 3. 执行
        try:
            log.info("Executing plan agent")
            from vibe3.agents.models import create_codeagent_command

            command = create_codeagent_command(
                role="planner",
                context_builder=lambda: spec.context,
                task=spec.task,
                handoff_kind=spec.handoff_kind,
                branch=branch,
                cwd=worktree.path,
                config=self.config,
            )
            result = self.execution_service.execute_with_callbacks(
                command=command,
                on_success=spec.on_success,
                on_failure=spec.on_failure,
                async_mode=async_mode,
            )
            log.info("Plan execution completed", success=result.success)
            return result
        finally:
            # 4. 清理资源（issue worktree 是长期的，不释放）
            log.info("Resource cleanup completed")

    def _handle_plan_success(
        self,
        result: CodeagentResult,
        issue_number: int,
        branch: str,
    ) -> None:
        """处理 plan 执行成功。

        职责：
        - 检查 plan_ref 是否存在
        - 如果存在：转换到 handoff 状态
        - 如果不存在：阻塞 issue

        Args:
            result: 执行结果
            issue_number: GitHub issue 编号
            branch: Git 分支名
        """
        log = logger.bind(
            domain="plan_usecase",
            action="handle_plan_success",
            issue=issue_number,
        )

        has_ref = self._require_plan_ref(
            issue_number=issue_number,
            branch=branch,
        )

        if has_ref:
            log.info("plan_ref found, transitioning to handoff")
            self._transition_to_handoff(issue_number)
        else:
            log.warning("plan_ref missing, blocking issue")
            self._block_issue(
                issue_number=issue_number,
                reason="Missing authoritative plan_ref",
            )

    def _handle_plan_failure(
        self,
        error: Exception,
        issue_number: int,
    ) -> None:
        """处理 plan 执行失败。

        职责：
        - 标记 issue 为 failed 状态

        Args:
            error: 异常对象
            issue_number: GitHub issue 编号
        """
        log = logger.bind(
            domain="plan_usecase",
            action="handle_plan_failure",
            issue=issue_number,
        )

        log.error("Plan execution failed", error=str(error))
        self._fail_issue(
            issue_number=issue_number,
            reason=str(error),
        )

    def create_plan_spec(
        self,
        request: PlanRequest,
        issue_number: int,
        branch: str,
    ) -> AgentSpec:
        """工厂方法：生成 Planner 的规格说明。

        Args:
            request: Plan 请求数据
            issue_number: GitHub issue 编号
            branch: Git 分支名

        Returns:
            AgentSpec 实例
        """
        # 构建 context
        context_builder = make_plan_context_builder(request, self.config)
        context = context_builder()

        return AgentSpec(
            role="planner",
            handoff_kind="plan",
            context=context,
            task=request.task_guidance,
            on_success=lambda r: self._handle_plan_success(r, issue_number, branch),
            on_failure=lambda e: self._handle_plan_failure(e, issue_number),
        )

    def _require_plan_ref(
        self,
        issue_number: int,
        branch: str,
    ) -> bool:
        """检查 plan_ref 是否存在。

        Args:
            issue_number: GitHub issue 编号
            branch: Git 分支名

        Returns:
            True 如果 plan_ref 存在，False 否则
        """
        return require_authoritative_ref(
            flow_service=self.flow_service,
            branch=branch,
            ref_name="plan_ref",
            issue_number=issue_number,
            reason="Missing authoritative plan_ref",
            actor="agent:plan",
            block_issue=lambda **kwargs: self._block_issue(**kwargs),
        )

    def _block_issue(
        self,
        issue_number: int,
        reason: str,
    ) -> None:
        """阻塞 issue。

        Args:
            issue_number: GitHub issue 编号
            reason: 阻塞原因
        """
        block_planner_noop_issue(
            issue_number=issue_number,
            reason=reason,
            actor="agent:plan",
        )

    def _transition_to_handoff(
        self,
        issue_number: int,
    ) -> None:
        """转换 issue 到 handoff 状态。

        Args:
            issue_number: GitHub issue 编号
        """
        confirm_plan_handoff(
            issue_number=issue_number,
            actor="agent:plan",
        )

    def _fail_issue(
        self,
        issue_number: int,
        reason: str,
    ) -> None:
        """标记 issue 为 failed 状态。

        Args:
            issue_number: GitHub issue 编号
            reason: 失败原因
        """
        fail_planner_issue(
            issue_number=issue_number,
            reason=reason,
            actor="agent:plan",
        )
