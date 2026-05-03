"""Prompt recipe manifest loader."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

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
            variants_raw = value.get("variants", {})
            variants = {
                variant_key: PromptRecipeVariant(
                    key=variant_key,
                    sections=_as_string_tuple(variant_value.get("sections")),
                )
                for variant_key, variant_value in variants_raw.items()
                if isinstance(variant_value, dict)
            }
            recipes[key] = PromptRecipeDefinition(
                key=key,
                template_key=str(value.get("template_key", key)),
                variants=variants,
                description=value.get("description"),
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
