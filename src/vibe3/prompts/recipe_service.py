"""Service wrapper around PromptAssembler for use in command and orchestra layers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.models import PromptRecipe, PromptRenderResult
from vibe3.prompts.provider_registry import ProviderRegistry


class PromptRecipeService:
    """Thin service wrapper that exposes render and dry_run_summary.

    Callers pass a PromptRecipe and a runtime_context dict; this service
    delegates resolution to PromptAssembler and returns a PromptRenderResult.
    """

    def __init__(
        self,
        prompts_path: Path | None = None,
        registry: ProviderRegistry | None = None,
    ) -> None:
        self._assembler = PromptAssembler(
            prompts_path=prompts_path,
            registry=registry,
        )

    def render(
        self,
        recipe: PromptRecipe,
        runtime_context: dict[str, Any],
    ) -> PromptRenderResult:
        """Render a recipe and return the full result with provenance."""
        return self._assembler.render(recipe, runtime_context)

    def dry_run_summary(
        self,
        recipe: PromptRecipe,
        runtime_context: dict[str, Any],
    ) -> str:
        """Return a human-readable dry-run summary for logging or CLI output."""
        result = self._assembler.render(recipe, runtime_context)
        lines = [
            f"Recipe key:      {result.recipe_key}",
            f"Template source: {result.template_source}",
            "Variable sources:",
        ]
        for prov in result.provenance:
            lines.append(
                f"  {prov.variable}: [{prov.source_kind.value}] "
                f"from {prov.resolved_from}"
            )
        lines.append("Rendered prompt:")
        lines.append(result.rendered_text)
        return "\n".join(lines)
