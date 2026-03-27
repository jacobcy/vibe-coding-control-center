"""Usecase layer for plan command orchestration."""

from dataclasses import dataclass
from pathlib import Path

from vibe3.clients.github_client import GitHubClient
from vibe3.config.settings import VibeConfig
from vibe3.models.flow import FlowStatusResponse
from vibe3.models.plan import PlanRequest, PlanScope
from vibe3.services.flow_service import FlowService
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
    ) -> None:
        self.config = config or VibeConfig.get_defaults()
        self.flow_service = flow_service or FlowService()
        self.github_client = github_client or GitHubClient()
        self.spec_ref_service = spec_ref_service or SpecRefService()

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
                    "Use 'vibe3 plan task <issue>' or bind a task to the current flow."
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

    @staticmethod
    def build_async_task_command(
        issue_number: int,
        instructions: str | None,
        agent: str | None,
        backend: str | None,
        model: str | None,
    ) -> list[str]:
        """Build async command invocation for `plan task`."""
        cmd = [
            "uv",
            "run",
            "python",
            "src/vibe3/cli.py",
            "plan",
            "task",
            str(issue_number),
        ]
        if instructions:
            cmd.append(instructions)
        if agent:
            cmd.extend(["--agent", agent])
        if backend:
            cmd.extend(["--backend", backend])
        if model:
            cmd.extend(["--model", model])
        return cmd

    @staticmethod
    def build_async_spec_command(
        file: Path | None,
        msg: str | None,
        instructions: str | None,
        agent: str | None,
        backend: str | None,
        model: str | None,
    ) -> list[str]:
        """Build async command invocation for `plan spec`."""
        cmd = ["uv", "run", "python", "src/vibe3/cli.py", "plan", "spec"]
        if file:
            cmd.extend(["--file", str(file)])
        if msg:
            cmd.extend(["--msg", msg])
        if instructions:
            cmd.append(instructions)
        if agent:
            cmd.extend(["--agent", agent])
        if backend:
            cmd.extend(["--backend", backend])
        if model:
            cmd.extend(["--model", model])
        return cmd

    def _build_issue_context(self, issue_number: int, heading: str) -> str | None:
        issue = self.github_client.view_issue(issue_number)
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
