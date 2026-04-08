"""Prompt rendering for Orchestra manager dispatch."""

from pathlib import Path

from vibe3.models.orchestration import IssueInfo
from vibe3.orchestra.config import OrchestraConfig
from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.models import (
    PromptRecipe,
    PromptRenderResult,
    PromptVariableSource,
    VariableSourceKind,
)
from vibe3.prompts.provider_registry import ProviderRegistry
from vibe3.prompts.template_loader import DEFAULT_PROMPTS_PATH


def render_manager_prompt(
    config: OrchestraConfig,
    issue: IssueInfo,
    prompts_path: Path | None = None,
) -> PromptRenderResult:
    """Render manager task instructions via PromptAssembler."""
    prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
    registry = ProviderRegistry()
    registry.register("manager.issue_number", lambda ctx: str(issue.number))
    registry.register("manager.issue_title", lambda ctx: issue.title)

    recipe = build_manager_recipe(config)
    assembler = PromptAssembler(prompts_path=prompts_path, registry=registry)
    return assembler.render(recipe, runtime_context={})


def build_manager_recipe(config: OrchestraConfig) -> PromptRecipe:
    """Build the PromptRecipe for manager dispatch."""
    ad = config.assignee_dispatch
    variables: dict[str, PromptVariableSource] = {
        "issue_number": PromptVariableSource(
            kind=VariableSourceKind.PROVIDER, provider="manager.issue_number"
        ),
        "issue_title": PromptVariableSource(
            kind=VariableSourceKind.PROVIDER, provider="manager.issue_title"
        ),
    }
    if ad.include_supervisor_content and ad.supervisor_file:
        variables["supervisor_content"] = PromptVariableSource(
            kind=VariableSourceKind.FILE, path=ad.supervisor_file
        )
    return PromptRecipe(
        template_key=ad.prompt_template,
        variables=variables,
        description="Manager task dispatch",
    )


def build_manager_command(
    config: OrchestraConfig,
    rendered_text: str,
) -> list[str]:
    """Build executable manager command for an issue."""
    cmd = ["uv", "run", "python", "-m", "vibe3", "run"]
    cmd.append("--async")
    # Worktree is now self-managed, no --worktree flag needed
    cmd.append(rendered_text)
    return cmd
