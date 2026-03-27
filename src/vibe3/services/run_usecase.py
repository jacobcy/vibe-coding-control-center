"""Usecase layer for run command orchestration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from vibe3.config.settings import RunConfig, VibeConfig
from vibe3.services.execution_pipeline import ExecutionRequest, run_execution_pipeline
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
        config: VibeConfig | None = None,
        flow_service: FlowService | None = None,
        execution_runner: Callable[[ExecutionRequest], Any] = run_execution_pipeline,
    ) -> None:
        self.config = config or VibeConfig.get_defaults()
        self.flow_service = flow_service or FlowService()
        self.execution_runner = execution_runner

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

    def create_execution_request(
        self,
        plan_file: str | None,
        instructions: str | None,
        agent: str | None,
        backend: str | None,
        model: str | None,
        context_builder: Callable[[str | None, VibeConfig], str],
        options_builder: Callable[..., Any],
        dry_run: bool,
    ) -> ExecutionRequest:
        """Build execution pipeline request for plan/lightweight mode."""
        task = instructions or self._default_run_prompt()
        metadata = {"plan_ref": plan_file} if plan_file else None
        return ExecutionRequest(
            role="executor",
            context_builder=lambda: context_builder(plan_file, self.config),
            options_builder=lambda: options_builder(
                self.config,
                agent,
                backend,
                model,
                section="run",
            ),
            task=task,
            dry_run=dry_run,
            handoff_kind="run",
            handoff_metadata=metadata,
        )

    def create_skill_execution_request(
        self,
        skill_name: str,
        skill_content: str,
        instructions: str | None,
        agent: str | None,
        backend: str | None,
        model: str | None,
        options_builder: Callable[..., Any],
        dry_run: bool,
    ) -> ExecutionRequest:
        """Build execution pipeline request for skill mode."""
        return ExecutionRequest(
            role="executor",
            context_builder=lambda: skill_content,
            options_builder=lambda: options_builder(
                self.config,
                agent,
                backend,
                model,
                section="run",
            ),
            task=instructions or f"Execute skill: {skill_name}",
            dry_run=dry_run,
            handoff_kind="run",
            handoff_metadata={"skill": skill_name},
        )

    @staticmethod
    def build_async_command(
        instructions: str | None,
        plan: Path | None,
        skill: str | None,
        agent: str | None,
        backend: str | None,
        model: str | None,
    ) -> list[str]:
        """Build async command invocation for `run`."""
        cmd = ["uv", "run", "python", "src/vibe3/cli.py", "run"]
        if instructions:
            cmd.append(instructions)
        if plan:
            cmd.extend(["--plan", str(plan)])
        if skill:
            cmd.extend(["--skill", skill])
        if agent:
            cmd.extend(["--agent", agent])
        if backend:
            cmd.extend(["--backend", backend])
        if model:
            cmd.extend(["--model", model])
        return cmd

    def transition_issue(self, branch: str) -> str | None:
        """Resolve linked task issue for post-run label transition."""
        flow = self.flow_service.get_flow_status(branch)
        if not flow or not flow.task_issue_number:
            return None
        return str(flow.task_issue_number)

    def execute(self, request: ExecutionRequest) -> Any:
        """Run execution pipeline through injected runner."""
        return self.execution_runner(request)

    @staticmethod
    def find_skill_file(
        skill_name: str,
        flow_service: FlowService | None = None,
    ) -> Path | None:
        """Find SKILL.md for a named skill under skills/ directory."""
        try:
            service = flow_service or FlowService()
            repo_root = Path(service.get_git_common_dir()).parent
        except Exception:
            repo_root = Path.cwd()

        candidate = repo_root / "skills" / skill_name / "SKILL.md"
        if candidate.exists():
            return candidate
        cwd_candidate = Path.cwd() / "skills" / skill_name / "SKILL.md"
        if cwd_candidate.exists():
            return cwd_candidate
        return None

    def _default_run_prompt(self) -> str | None:
        run_config: RunConfig | None = getattr(self.config, "run", None)
        if run_config:
            return run_config.run_prompt
        return None
