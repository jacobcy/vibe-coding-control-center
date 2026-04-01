"""Usecase layer for run command orchestration.

Migrated from vibe3.services.run_usecase.
"""

from dataclasses import dataclass
from pathlib import Path

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
