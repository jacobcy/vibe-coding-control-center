"""Prompt recipe manifest loader."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from vibe3.prompts.models import (
    LoadedPromptRecipeDefinition,
    PromptRecipeKind,
    PromptRecipeVariantSpec,
    PromptSectionSpec,
    PromptVariableSource,
    VariableSourceKind,
)

DEFAULT_PROMPT_RECIPES_PATH = Path("config/prompts/prompt-recipes.yaml")

PromptProvider = Callable[[], str | None]


@dataclass(frozen=True)
class PromptRecipeVariant:
    """A named section ordering for one prompt recipe."""

    key: str
    sections: tuple[str, ...]


@dataclass(frozen=True)
class PromptRecipeDefinition:
    """One prompt recipe with runtime-selectable variants."""

    key: str
    template_key: str
    variants: dict[str, PromptRecipeVariant]
    description: str | None = None
    # New fields for unified schema
    kind: PromptRecipeKind = PromptRecipeKind.SECTION
    loaded_definition: LoadedPromptRecipeDefinition | None = None
    variables: dict[str, PromptVariableSource] | None = None

    def variant(self, key: str) -> PromptRecipeVariant:
        """Return a configured variant by key."""
        try:
            return self.variants[key]
        except KeyError as exc:
            message = f"Prompt recipe variant not found: {self.key}.{key}"
            raise KeyError(message) from exc


@dataclass(frozen=True)
class PromptManifest:
    """Loaded prompt recipe manifest."""

    recipes: dict[str, PromptRecipeDefinition]

    @classmethod
    def load_default(cls) -> "PromptManifest":
        """Load prompt recipes from the repository config directory."""
        return cls.load(_resolve_repo_path(DEFAULT_PROMPT_RECIPES_PATH))

    @classmethod
    def load(cls, recipes_path: Path) -> "PromptManifest":
        """Load recipe YAML file.

        Raises:
            FileNotFoundError: If recipes_path does not exist.
            ValueError: If recipes_path exists but contains invalid YAML.
        """
        if not recipes_path.exists():
            raise FileNotFoundError(
                f"Prompt recipes file not found: {recipes_path}. "
                "Please ensure config/prompts/prompt-recipes.yaml exists "
                "in the repository."
            )

        recipes_raw = _read_yaml(recipes_path).get("recipes", {})

        recipes: dict[str, PromptRecipeDefinition] = {}
        for key, value in recipes_raw.items():
            if not isinstance(value, dict):
                continue

            # Parse kind field
            kind_str = value.get("kind", "section_recipe")
            if kind_str in {"section_recipe", "template_recipe"}:
                kind = PromptRecipeKind(kind_str)
            else:
                kind = PromptRecipeKind.SECTION

            # Parse template_key
            template_key = str(value.get("template_key", key))

            # Parse variables (for template_recipe)
            variables_raw = value.get("variables", {})
            variables: dict[str, PromptVariableSource] | None = None
            if variables_raw and isinstance(variables_raw, dict):
                variables = {
                    var_key: _parse_variable_source(var_value)
                    for var_key, var_value in variables_raw.items()
                    if isinstance(var_value, dict)
                }

            # Parse variants (for section_recipe)
            variants_raw = value.get("variants", {})
            variants: dict[str, PromptRecipeVariant] = {}
            loaded_variants: dict[str, PromptRecipeVariantSpec] = {}

            for variant_key, variant_value in variants_raw.items():
                if not isinstance(variant_value, dict):
                    continue

                sections_raw = variant_value.get("sections", [])
                # Parse sections with new schema support
                section_specs = _parse_section_specs(sections_raw)

                # Build legacy variant for backward compatibility
                sections_tuple = tuple(spec.key for spec in section_specs)
                variants[variant_key] = PromptRecipeVariant(
                    key=variant_key,
                    sections=sections_tuple,
                )

                # Build loaded variant spec
                loaded_variants[variant_key] = PromptRecipeVariantSpec(
                    key=variant_key,
                    sections=section_specs,
                )

            # Build loaded definition
            loaded_def = LoadedPromptRecipeDefinition(
                key=key,
                kind=kind,
                template_key=template_key,
                variants=loaded_variants,
                variables=variables or {},
                description=value.get("description"),
            )

            recipes[key] = PromptRecipeDefinition(
                key=key,
                template_key=template_key,
                variants=variants,
                description=value.get("description"),
                kind=kind,
                loaded_definition=loaded_def,
                variables=variables,
            )

        return cls(recipes=recipes)

    def recipe(self, key: str) -> PromptRecipeDefinition:
        """Return a configured recipe by key."""
        try:
            return self.recipes[key]
        except KeyError as exc:
            raise KeyError(f"Prompt recipe not found: {key}") from exc

    def render_sections(
        self,
        recipe_key: str,
        variant_key: str,
        providers: dict[str, PromptProvider],
    ) -> str:
        """Render configured sections through provider-backed section keys.

        Raises:
            KeyError: If recipe, variant, or provider not found.
        """
        rendered: list[str] = []
        recipe_def = self.recipe(recipe_key)
        variant_def = recipe_def.variant(variant_key)

        for section_key in variant_def.sections:
            provider = providers.get(section_key)
            if provider is None:
                logger.bind(
                    domain="prompt_manifest",
                    recipe=recipe_key,
                    variant=variant_key,
                    missing_section=section_key,
                    available_providers=list(providers.keys()),
                ).error("Prompt section provider not registered")
                raise KeyError(
                    f"Prompt section provider not registered: {section_key}. "
                    f"Check configuration for recipe '{recipe_key}' "
                    f"variant '{variant_key}'."
                )
            value = provider()
            if value:
                rendered.append(value)
        return "\n\n---\n\n".join(rendered)


def _resolve_repo_path(relative_path: Path) -> Path:
    """Resolve a config path against repo root, falling back to cwd."""
    try:
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        repo_path = repo_root / relative_path
        if repo_path.exists():
            return repo_path
    except Exception:  # pragma: no cover
        pass
    return relative_path


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as stream:
            raw = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        logger.bind(domain="prompt_manifest", path=str(path)).warning(
            f"Invalid YAML in prompt manifest: {exc}"
        )
        return {}
    except OSError as exc:
        logger.bind(domain="prompt_manifest", path=str(path)).warning(
            f"Cannot read prompt manifest: {exc}"
        )
        return {}
    return raw if isinstance(raw, dict) else {}


def _as_string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _parse_section_specs(sections_raw: Any) -> tuple[PromptSectionSpec, ...]:
    """Parse sections list supporting both string and object format."""
    if not isinstance(sections_raw, list):
        return ()

    specs: list[PromptSectionSpec] = []
    for item in sections_raw:
        if isinstance(item, str):
            # Legacy format: just a string key
            specs.append(PromptSectionSpec(key=item))
        elif isinstance(item, dict) and "key" in item:
            # New format: object with key and optional source
            key = str(item["key"])
            source_raw = item.get("source")
            if isinstance(source_raw, dict):
                source = _parse_variable_source(source_raw)
            else:
                source = None
            specs.append(PromptSectionSpec(key=key, source=source))

    return tuple(specs)


def _parse_variable_source(raw: dict[str, Any]) -> PromptVariableSource:
    """Parse a variable source declaration."""
    kind_str = raw.get("kind", "literal")
    valid_kinds = {e.value for e in VariableSourceKind}
    if kind_str in valid_kinds:
        kind = VariableSourceKind(kind_str)
    else:
        kind = VariableSourceKind.LITERAL

    return PromptVariableSource(
        kind=kind,
        value=raw.get("value"),
        skill=raw.get("skill"),
        path=raw.get("path"),
        command=raw.get("command"),
        provider=raw.get("provider"),
        context_key=raw.get("context_key"),
        kwargs=raw.get("kwargs", {}),
    )
