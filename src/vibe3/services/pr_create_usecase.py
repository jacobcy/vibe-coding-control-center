"""Usecase layer for pr create command orchestration."""

from dataclasses import dataclass
from typing import Protocol

from loguru import logger
from rich.console import Console
from rich.prompt import Prompt

from vibe3.clients.ai_suggestion_client import AISuggestionClient
from vibe3.config.settings import VibeConfig
from vibe3.prompts.template_loader import _resolve_prompts_path
from vibe3.services.base_resolution_usecase import BaseResolutionUsecase
from vibe3.services.flow_service import FlowService
from vibe3.services.task_binding_guard import ensure_task_issue_bound


@dataclass(frozen=True)
class PRCreateResult:
    """Structured result from the pr create usecase."""

    title: str
    body: str
    base_branch: str
    actor: str


class BaseResolver(Protocol):
    """Protocol for base branch resolution."""

    def resolve_pr_create_base(self, requested_base: str | None) -> str: ...
    def collect_branch_material(self, base_branch: str, branch: str) -> object: ...


class PRCreateUsecase:
    """Coordinate PR creation: AI suggestions, title resolution, flow checks."""

    def __init__(
        self,
        flow_service: FlowService | None = None,
        base_resolver: BaseResolver | None = None,
    ) -> None:
        self._flow_service = FlowService() if flow_service is None else flow_service
        self._base_resolver = (
            BaseResolutionUsecase() if base_resolver is None else base_resolver
        )

    def check_flow_task(self, branch: str, *, yes: bool = False) -> None:
        """Require current flow to have task bound unless bypassed by --yes."""
        flow_status = self._flow_service.get_flow_status(branch)
        ensure_task_issue_bound(
            flow_status,
            yes=yes,
            force_command="vibe3 pr create --yes",
        )
        if yes and (flow_status is None or flow_status.task_issue_number is None):
            logger.warning("Bypassing missing task binding via --yes")

    def suggest_content(
        self,
        branch: str,
        base_branch: str,
        interactive: bool,
    ) -> tuple[str, str]:
        """Run AI suggestion flow and return (title, body).

        Falls back to empty strings when AI is unavailable or produces
        no result.
        """
        material = self._base_resolver.collect_branch_material(
            base_branch=base_branch,
            branch=branch,
        )
        commits = getattr(material, "commits", [])
        changed_files = getattr(material, "changed_files", [])

        if not commits:
            if interactive:
                Console().print(
                    "[yellow]No commits found, cannot generate AI suggestions[/]"
                )
            return ("", "")

        config = VibeConfig.get_defaults()
        prompts_path = _resolve_prompts_path()
        ai_client = AISuggestionClient(config.ai, prompts_path=prompts_path)
        result = ai_client.suggest_pr_content(commits, changed_files)

        if not result:
            if interactive:
                Console().print(
                    "[yellow]AI suggestion unavailable, using manual input[/]"
                )
            return ("", "")

        suggested_title, suggested_body = result
        title = self._resolve_field(suggested_title or "", "title", interactive)
        body = self._resolve_field(suggested_body or "", "body", interactive)
        return (title, body)

    def resolve_title(self, title: str, ai_title: str, interactive: bool) -> str:
        """Return final PR title, prompting if needed."""
        if title:
            return title
        if ai_title:
            return ai_title
        if interactive:
            return Prompt.ask("Enter PR title")
        raise ValueError("PR title is required")

    @staticmethod
    def _resolve_field(
        value: str,
        field_name: str,
        interactive: bool,
    ) -> str:
        """Accept or reject a single AI-suggested field."""
        if not value:
            return ""
        if not interactive:
            return value
        console = Console()
        display = value if field_name == "title" else f"\n{value}"
        console.print(f"\n[bold]Suggested {field_name}:[/]{display}")
        use_it = Prompt.ask(f"Use this {field_name}?", choices=["y", "n"], default="y")
        if use_it == "y":
            return value
        if field_name == "title":
            return Prompt.ask("Enter PR title")
        return ""
