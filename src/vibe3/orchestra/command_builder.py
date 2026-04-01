"""Command builder for Orchestra - constructs executable agent commands."""

from pathlib import Path
from typing import TYPE_CHECKING

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.prompts import (
    build_manager_command,
    build_manager_recipe,
    render_manager_prompt,
)

if TYPE_CHECKING:
    from vibe3.models.orchestration import IssueInfo
    from vibe3.prompts.models import PromptRecipe, PromptRenderResult


class CommandBuilder:
    """Constructs executable commands for various orchestra agents."""

    def __init__(
        self,
        config: OrchestraConfig,
        prompts_path: Path | None = None,
    ):
        self.config = config
        from vibe3.prompts.template_loader import DEFAULT_PROMPTS_PATH

        self.prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
        # Set after build_manager_command; used for dry-run provenance logging
        self.last_manager_render_result: "PromptRenderResult | None" = None

    def build_manager_command(self, issue: "IssueInfo") -> list[str]:
        """Build executable manager command for an issue."""
        render_result = render_manager_prompt(
            self.config, issue, prompts_path=self.prompts_path
        )
        self.last_manager_render_result = render_result
        return build_manager_command(self.config, render_result.rendered_text)

    def build_manager_recipe(self) -> "PromptRecipe":
        """Build the PromptRecipe for manager dispatch."""
        return build_manager_recipe(self.config)

    def build_pr_review_command(self, pr_number: int) -> list[str]:
        """Build executable PR review command."""
        cmd = ["uv", "run", "python", "-m", "vibe3", "review", "pr", str(pr_number)]
        if self.config.pr_review_dispatch.async_mode:
            cmd.append("--async")
        if self.config.pr_review_dispatch.use_worktree:
            cmd.append("--worktree")
        return cmd
