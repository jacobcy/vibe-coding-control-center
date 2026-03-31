"""Prompt recipe validation and sample rendering.

Public API:
- ``PromptValidationResult`` - frozen dataclass holding validation outcome
- ``ValidationIssue`` - frozen dataclass for individual validation errors
- ``PromptValidationService`` - validates template keys and renders sample prompts
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vibe3.prompts.models import (
    PromptRecipe,
    PromptVariableProvenance,
    VariableSourceKind,
)
from vibe3.prompts.provider_registry import ProviderRegistry
from vibe3.prompts.template_loader import (
    DEFAULT_PROMPTS_PATH,
    resolve_prompt_template,
)

# Matches {variable_name} in Python format strings
_TEMPLATE_VAR_RE = re.compile(r"(?<!\{)\{([a-zA-Z_][a-zA-Z0-9_]*)\}(?!\})")


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation error or warning."""

    kind: str
    message: str


@dataclass(frozen=True)
class PromptValidationResult:
    """Result of validating a template key or rendering a recipe sample."""

    template_key: str
    is_valid: bool
    issues: tuple[ValidationIssue, ...]
    preview_text: str | None
    provenance: tuple[PromptVariableProvenance, ...] | None
    required_variables: frozenset[str] = frozenset()


class PromptValidationService:
    """Validate prompt recipe contracts and render sample previews.

    Validation does not execute COMMAND or PROVIDER sources — it substitutes
    placeholder text so the template can be rendered without side effects.
    """

    def __init__(
        self,
        prompts_path: Path | None = None,
        registry: ProviderRegistry | None = None,
    ) -> None:
        self._prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
        self._registry = registry or ProviderRegistry()

    def validate_template_key(self, template_key: str) -> PromptValidationResult:
        """Validate that a template key exists and report its required variables."""
        template = resolve_prompt_template(template_key, self._prompts_path)
        if template is None:
            return PromptValidationResult(
                template_key=template_key,
                is_valid=False,
                issues=(
                    ValidationIssue(
                        kind="missing_template",
                        message=(
                            f"Template key '{template_key}'"
                            " not found in prompts.yaml"
                        ),
                    ),
                ),
                preview_text=None,
                provenance=None,
                required_variables=frozenset(),
            )

        required = frozenset(_TEMPLATE_VAR_RE.findall(template))
        return PromptValidationResult(
            template_key=template_key,
            is_valid=True,
            issues=(),
            preview_text=None,
            provenance=None,
            required_variables=required,
        )

    def render_sample(self, recipe: PromptRecipe) -> PromptValidationResult:
        """Render a recipe with sample/placeholder values."""
        template = resolve_prompt_template(recipe.template_key, self._prompts_path)
        if template is None:
            return PromptValidationResult(
                template_key=recipe.template_key,
                is_valid=False,
                issues=(
                    ValidationIssue(
                        kind="missing_template",
                        message=(
                            f"Template key '{recipe.template_key}' not found"
                            " in prompts.yaml"
                        ),
                    ),
                ),
                preview_text=None,
                provenance=None,
            )

        required_vars = frozenset(_TEMPLATE_VAR_RE.findall(template))
        issues: list[ValidationIssue] = []

        missing = required_vars - set(recipe.variables.keys())
        for var in sorted(missing):
            issues.append(
                ValidationIssue(
                    kind="missing_variable",
                    message=(
                        f"Variable '{var}' required by template '{recipe.template_key}'"
                        " but not declared in recipe"
                    ),
                )
            )

        if missing:
            return PromptValidationResult(
                template_key=recipe.template_key,
                is_valid=False,
                issues=tuple(issues),
                preview_text=None,
                provenance=None,
                required_variables=required_vars,
            )

        # Resolve variables with sample substitution for PROVIDER/COMMAND
        resolved: dict[str, str] = {}
        provenance_list: list[PromptVariableProvenance] = []

        for var, source in recipe.variables.items():
            value, issue = self._resolve_sample(var, source)
            if issue:
                issues.append(issue)
            resolved[var] = value
            provenance_list.append(
                PromptVariableProvenance(
                    variable=var,
                    source_kind=source.kind,
                    resolved_from=_describe_source(source),
                    value_preview=value[:200],
                )
            )

        try:
            rendered = template.format(**resolved)
        except (KeyError, ValueError) as exc:
            issues.append(
                ValidationIssue(
                    kind="render_error",
                    message=f"Template rendering failed: {exc}",
                )
            )
            return PromptValidationResult(
                template_key=recipe.template_key,
                is_valid=False,
                issues=tuple(issues),
                preview_text=None,
                provenance=tuple(provenance_list),
                required_variables=required_vars,
            )

        return PromptValidationResult(
            template_key=recipe.template_key,
            is_valid=not any(i.kind not in {"file_not_found"} for i in issues),
            issues=tuple(issues),
            preview_text=rendered,
            provenance=tuple(provenance_list),
            required_variables=required_vars,
        )

    def _resolve_sample(
        self, var: str, source: Any
    ) -> tuple[str, ValidationIssue | None]:
        """Resolve a variable source for sample rendering."""
        kind = source.kind

        if kind == VariableSourceKind.LITERAL:
            return source.value or "", None

        if kind == VariableSourceKind.PROVIDER:
            return f"<provider:{source.provider}>", None

        if kind == VariableSourceKind.COMMAND:
            return f"<command:{source.command}>", None

        if kind == VariableSourceKind.FILE:
            path = Path(source.path) if source.path else None
            if path is None or not path.exists():
                return "", ValidationIssue(
                    kind="file_not_found",
                    message=f"File not found for variable '{var}': {source.path}",
                )
            try:
                return path.read_text(encoding="utf-8"), None
            except OSError as exc:
                return "", ValidationIssue(
                    kind="file_not_found",
                    message=f"Cannot read file for variable '{var}': {exc}",
                )

        if kind == VariableSourceKind.SKILL:
            from vibe3.services.run_usecase import RunUsecase

            skill_name = source.skill or ""
            skill_file = RunUsecase.find_skill_file(skill_name) if skill_name else None
            if skill_file is None:
                return "", ValidationIssue(
                    kind="skill_not_found",
                    message=f"Skill not found for variable '{var}': {skill_name}",
                )
            try:
                return skill_file.read_text(encoding="utf-8"), None
            except OSError as exc:
                return "", ValidationIssue(
                    kind="skill_not_found",
                    message=f"Cannot read skill for variable '{var}': {exc}",
                )

        return "", None


def _describe_source(source: Any) -> str:
    """Return a human-readable description of a variable source."""
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
