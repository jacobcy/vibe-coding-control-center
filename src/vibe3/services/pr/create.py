"""Usecase layer for pr create command orchestration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from rich.console import Console
from rich.prompt import Prompt

from vibe3.analysis import build_review_observation
from vibe3.clients import AIClient, AISuggestionClient, BaseResolver, GitClient
from vibe3.config import VibeConfig
from vibe3.prompts import resolve_prompts_path
from vibe3.services.pr.base_resolution import BaseResolutionUsecase
from vibe3.services.shared.binding_guard import ensure_task_issue_bound

if TYPE_CHECKING:
    from vibe3.services.protocols import FlowQueryProtocol


@dataclass(frozen=True)
class PRCreateResult:
    """Structured result from the pr create usecase."""

    title: str
    body: str
    base_branch: str
    actor: str


class BranchMaterial:
    """Branch analysis material for AI suggestions."""

    def __init__(
        self,
        commits: list[str],
        changed_files: list[str],
        body: str,
        base_branch: str,
        actor: str,
    ) -> None:
        self.commits = commits
        self.changed_files = changed_files
        self.body = body
        self.base_branch = base_branch
        self.actor = actor


def _build_inspect_summary(branch: str, base_branch: str) -> str:
    """Build exact Git/Kernel evidence for AI prompt context."""
    try:
        git = GitClient()
        if git.get_current_branch() != branch:
            return ""
        repo_root = Path(git.get_worktree_root())
        result = build_review_observation(
            requested_base=base_branch,
            resolved_base=base_branch,
            git=git,
            manifest_path=repo_root / "config" / "v3" / "review_kernel.yaml",
        )
        if result.status == "error":
            return ""

        lines = [
            "## Review Observation (inspect base)",
            f"- Status: {result.status}",
            f"- Committed files: {result.changes.summary.committed.files}",
            f"- Staged files: {result.changes.summary.staged.files}",
            f"- Unstaged files: {result.changes.summary.unstaged.files}",
            f"- Untracked files: {result.changes.summary.untracked.files}",
            "- Runtime impact analysis: disabled (benchmark gate failed)",
        ]
        if result.kernel is not None:
            lines.append(f"- Kernel impact: {result.kernel.impact.value}")
            hits = result.kernel.architecture_hits + result.kernel.review_hits
            if hits:
                lines.append("- Kernel files:")
                lines.extend(f"  - {hit.path}" for hit in hits)
        if result.review is not None:
            lines.append(f"- Minimum review depth: {result.review.minimum_depth.value}")
        return "\n".join(lines)
    except Exception:
        return ""  # Gracefully degrade - inspect data is optional


def _enrich_changed_files(changed_files: list[str], branch: str, base: str) -> str:
    """Enrich file list with LOC info from git diff for AI context."""
    try:
        from vibe3.clients import GitClient
        from vibe3.models import BranchSource

        git = GitClient()
        source = BranchSource(branch=branch, base=base)
        numstat = git.get_numstat(source)
        if not numstat:
            return "\n".join(f"- {f}" for f in changed_files)

        loc_map: dict[str, int] = {}
        for line in numstat.split("\n"):
            parts = line.split("\t")
            if len(parts) >= 3:
                try:
                    added = int(parts[0]) if parts[0] != "-" else 0
                    removed = int(parts[1]) if parts[1] != "-" else 0
                    loc_map[parts[2]] = added - removed
                except ValueError:
                    pass

        lines = ["## Changed Files"]
        for f in changed_files:
            delta = loc_map.get(f, 0)
            sign = "+" if delta >= 0 else ""
            lines.append(f"- {f} ({sign}{delta} LOC)")
        return "\n".join(lines)
    except Exception:
        return "\n".join(f"- {f}" for f in changed_files)


class PRCreateUsecase:
    """Coordinate PR creation: AI suggestions, title resolution, flow checks."""

    def __init__(
        self,
        flow_service: FlowQueryProtocol | None = None,
        base_resolver: BaseResolver | None = None,
    ) -> None:
        self._service_input = flow_service
        self._base_resolver = (
            BaseResolutionUsecase() if base_resolver is None else base_resolver
        )

    @property
    def _flow_service(self) -> FlowQueryProtocol:
        """Return injected flow service (required)."""
        if self._service_input is None:
            raise RuntimeError(
                "PRCreateUsecase requires flow_service to be injected. "
                "Pass a FlowQueryProtocol instance to the constructor."
            )
        return self._service_input

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

        # Collect inspect base data for richer AI context
        inspect_summary = _build_inspect_summary(branch, base_branch)
        # Enrich file list with LOC from git diff
        enriched_files = _enrich_changed_files(changed_files, branch, base_branch)

        if not commits:
            if interactive:
                Console().print(
                    "[yellow]No commits found, cannot generate AI suggestions[/]"
                )
            return ("", "")

        config = VibeConfig.get_defaults()
        prompts_path = resolve_prompts_path()
        api_key = os.environ.get(config.ai.api_key_env, "")
        ai_client_instance = AIClient(
            api_key=api_key,
            base_url=config.ai.base_url,
            model=config.ai.model,
            timeout=config.ai.timeout,
        )
        ai_client = AISuggestionClient(
            ai_client=ai_client_instance, prompts_path=prompts_path
        )
        result = ai_client.suggest_pr_content(
            commits,
            changed_files,
            inspect_summary=inspect_summary,
            enriched_files=enriched_files,
        )

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
