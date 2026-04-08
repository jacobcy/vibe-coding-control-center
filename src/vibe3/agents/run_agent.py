"""Usecase layer for run command orchestration.

Migrated from vibe3.services.run_usecase.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from vibe3.services.flow_service import FlowService


@dataclass
class RunCommandSummary:
    """UI-facing run mode summary."""

    mode: str
    plan_file: str | None = None
    message: str | None = None


class RunUsecase:
    """Coordinate run command routing with reusable services."""

    def __init__(
        self,
        flow_service: FlowService | None = None,
    ) -> None:
        self.flow_service = flow_service or FlowService()

    def resolve_run_mode(
        self,
        branch: str,
        instructions: str | None,
        plan: Path | None,
        skill: str | None,
    ) -> RunCommandSummary:
        """Resolve command mode before execution."""
        if skill:
            return RunCommandSummary(mode="skill", message=skill)
        if plan:
            return RunCommandSummary(mode="plan", plan_file=str(plan))
        if instructions:
            preview = instructions[:60]
            suffix = "..." if len(instructions) > 60 else ""
            return RunCommandSummary(
                mode="lightweight",
                message=f"-> Task: {preview}{suffix}",
            )
        flow = self.flow_service.get_flow_status(branch)
        if flow and flow.plan_ref:
            return RunCommandSummary(mode="flow_plan", plan_file=str(flow.plan_ref))
        raise ValueError(
            "No plan specified.\n"
            "Use one of:\n"
            "  vibe3 run <instructions>        # Lightweight mode\n"
            "  vibe3 run --plan <file>         # With plan file\n"
            "  vibe3 run --skill <name>        # With skill"
        )

    def transition_issue(self, branch: str) -> str | None:
        """Resolve linked task issue for post-run label transition."""
        flow = self.flow_service.get_flow_status(branch)
        if not flow or not flow.task_issue_number:
            return None
        return str(flow.task_issue_number)

    def build_lifecycle_callbacks(
        self,
        issue_number: int,
        branch: str,
        flow_service: FlowService,  # noqa: ARG002 - kept for API compatibility
    ) -> tuple[Callable[[object], None], Callable[[Exception], None]]:
        """生成执行成功/失败时的状态机流转回调。

        Flow:
            on_success: publish ReportRefRequired → IssueStateChanged(HANDOFF)
            on_failure: publish IssueFailed(reason)

        Args:
            issue_number: Issue 编号
            branch: 当前分支
            flow_service: Flow 服务实例 (deprecated: events create their own)

        Returns:
            (on_success, on_failure) 回调元组
        """
        from vibe3.domain.events import (
            IssueFailed,
            IssueStateChanged,
            ReportRefRequired,
        )
        from vibe3.domain.publisher import publish
        from vibe3.models.orchestration import IssueState

        def on_success(result: object) -> None:
            """执行成功：验证报告引用并确认 Issue 状态。"""
            # Publish ReportRefRequired event
            report_required_event = ReportRefRequired(
                issue_number=issue_number,
                branch=branch,
                ref_name="report_ref",
                reason=(
                    "executor output artifact was saved, but no authoritative "
                    "report_ref was registered. Write a canonical report "
                    "document and run handoff report."
                ),
                actor="agent:run",
            )
            publish(report_required_event)

            # Note: The handler will block the issue if ref is missing
            # For now, we still proceed to state transition
            # (the handler's validation outcome can be checked if needed)

            # Publish IssueStateChanged event
            state_changed_event = IssueStateChanged(
                issue_number=issue_number,
                from_state=None,  # Will be detected by handler
                to_state=IssueState.HANDOFF.value,
                actor="agent:run",
            )
            publish(state_changed_event)

        def on_failure(error: Exception) -> None:
            """执行失败：发布 Issue 失败事件。"""
            # Publish IssueFailed event
            failed_event = IssueFailed(
                issue_number=issue_number,
                reason=str(error),
                actor="agent:run",
            )
            publish(failed_event)

        return on_success, on_failure

    @staticmethod
    def find_skill_file(
        skill_name: str,
        flow_service: FlowService | None = None,
    ) -> Path | None:
        """Find SKILL.md for a named skill under skills/ directory."""
        cwd_candidate = Path.cwd() / "skills" / skill_name / "SKILL.md"
        if cwd_candidate.exists():
            return cwd_candidate

        try:
            service = flow_service or FlowService()
            repo_root = Path(service.get_git_common_dir()).parent
        except Exception:
            repo_root = Path.cwd()

        candidate = repo_root / "skills" / skill_name / "SKILL.md"
        if candidate.exists():
            return candidate
        return None
