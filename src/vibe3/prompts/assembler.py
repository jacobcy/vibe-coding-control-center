"""PromptAssembler: render a PromptRecipe into a PromptRenderResult."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from vibe3.prompts.builtin_providers import resolve_source
from vibe3.prompts.exceptions import MissingVariableError, TemplateNotFoundError
from vibe3.prompts.models import (
    PromptRecipe,
    PromptRenderResult,
    PromptVariableProvenance,
    PromptVariableSource,
    VariableSourceKind,
)
from vibe3.prompts.provider_registry import ProviderRegistry
from vibe3.prompts.template_loader import (
    DEFAULT_PROMPTS_PATH,
    resolve_prompt_template,
)

# Matches {variable_name} in Python format strings (single braces, not {{ or }})
_TEMPLATE_VAR_RE = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")


def _extract_template_variables(template: str) -> set[str]:
    """Return all {variable_name} placeholders in a template string."""
    return set(_TEMPLATE_VAR_RE.findall(template))


class PromptAssembler:
    """Renders a PromptRecipe into a PromptRenderResult.

    - Loads the template text via resolve_prompt_template.
    - Validates that declared variables match template placeholders.
    - Resolves each variable via builtin_providers.resolve_source.
    - Records provenance for every resolved variable.
    """

    def __init__(
        self,
        prompts_path: Path | None = None,
        registry: ProviderRegistry | None = None,
    ) -> None:
        self._prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
        self._registry = registry or ProviderRegistry()

    def render(
        self,
        recipe: PromptRecipe,
        runtime_context: dict[str, Any],
    ) -> PromptRenderResult:
        """Render a recipe into a PromptRenderResult."""
        template = resolve_prompt_template(recipe.template_key, self._prompts_path)
        if template is None:
            raise TemplateNotFoundError(recipe.template_key)

        required_vars = _extract_template_variables(template)

        # Fail fast on missing variable sources
        for var in sorted(required_vars):
            if var not in recipe.variables:
                raise MissingVariableError(
                    variable=var, template_key=recipe.template_key
                )

        # Resolve each declared variable and build provenance
        resolved: dict[str, str] = {}
        provenance_list: list[PromptVariableProvenance] = []

        for var, source in recipe.variables.items():
            value = resolve_source(source, runtime_context, self._registry)
            resolved[var] = value
            resolved_from = _describe_source(source)
            provenance_list.append(
                PromptVariableProvenance(
                    variable=var,
                    source_kind=source.kind,
                    resolved_from=resolved_from,
                    value_preview=value[:200],
                )
            )

        rendered_text = template.format(**resolved)
        template_source = str(
            self._prompts_path
            if self._prompts_path.is_absolute()
            else Path.cwd() / self._prompts_path
        )

        return PromptRenderResult(
            recipe_key=recipe.template_key,
            template_source=template_source,
            rendered_text=rendered_text,
            provenance=tuple(provenance_list),
        )


def _describe_source(source: PromptVariableSource) -> str:
    """Return a human-readable description of where a variable came from."""
    if source.kind == VariableSourceKind.LITERAL:
        return "literal"
    if source.kind == VariableSourceKind.SKILL:
        return f"skill:{source.skill}"
    if source.kind == VariableSourceKind.FILE:
        return f"file:{source.path}"
    if source.kind == VariableSourceKind.COMMAND:
        return f"command:{source.command}"
    if source.kind == VariableSourceKind.PROVIDER:
        return f"provider:{source.provider}"
    return "unknown"
