"""Tests for prompt recipe manifests."""

from pathlib import Path

import pytest

from vibe3.prompts.manifest import (
    DEFAULT_PROMPT_RECIPES_PATH,
    PromptManifest,
    _resolve_repo_path,
)


def test_prompt_manifest_loads_recipe_variants_from_yaml(tmp_path: Path) -> None:
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  demo.recipe:
    template_key: demo.template
    variants:
      default:
        sections:
          - demo.first
          - demo.second
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)

    recipe = manifest.recipe("demo.recipe")
    assert recipe.template_key == "demo.template"
    assert recipe.variant("default").sections == ("demo.first", "demo.second")


def test_prompt_manifest_resolves_migrated_default_path() -> None:
    assert DEFAULT_PROMPT_RECIPES_PATH == Path("config/v3/prompt-recipes.yaml")

    resolved = _resolve_repo_path(DEFAULT_PROMPT_RECIPES_PATH)

    assert resolved == Path.cwd() / "config/v3/prompt-recipes.yaml"


def test_prompt_manifest_renders_configured_sections(tmp_path: Path) -> None:
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  demo.recipe:
    variants:
      default:
        sections:
          - demo.first
          - demo.empty
          - demo.second
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)

    rendered = manifest.render_sections(
        "demo.recipe",
        "default",
        providers={
            "demo.first": lambda: "first",
            "demo.empty": lambda: None,
            "demo.second": lambda: "second",
        },
    )

    assert rendered == "first\n\n---\n\nsecond"


def test_prompt_manifest_raises_on_missing_file(tmp_path: Path) -> None:
    """Verify FileNotFoundError when recipes file is missing."""
    missing_path = tmp_path / "missing-recipes.yaml"

    with pytest.raises(FileNotFoundError, match="Prompt recipes file not found"):
        PromptManifest.load(missing_path)


def test_prompt_manifest_raises_on_missing_recipe(tmp_path: Path) -> None:
    """Verify KeyError when recipe key is not found."""
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  demo.recipe:
    variants:
      default:
        sections: []
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)

    with pytest.raises(KeyError, match="Prompt recipe not found: missing.recipe"):
        manifest.recipe("missing.recipe")


def test_prompt_manifest_raises_on_missing_variant(tmp_path: Path) -> None:
    """Verify KeyError when variant key is not found."""
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  demo.recipe:
    variants:
      default:
        sections: []
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)

    with pytest.raises(KeyError, match="Prompt recipe variant not found"):
        manifest.recipe("demo.recipe").variant("missing_variant")


def test_render_sections_raises_on_missing_provider(tmp_path: Path) -> None:
    """Verify KeyError with full context when provider is missing."""
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  demo.recipe:
    variants:
      default:
        sections:
          - demo.missing
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)

    with pytest.raises(KeyError, match="Prompt section provider not registered"):
        manifest.render_sections("demo.recipe", "default", providers={})


def test_render_sections_error_includes_context(tmp_path: Path) -> None:
    """Verify error message includes recipe, variant, and available providers."""
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  demo.recipe:
    variants:
      default:
        sections:
          - demo.missing
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)

    try:
        manifest.render_sections(
            "demo.recipe", "default", providers={"demo.other": lambda: "test"}
        )
    except KeyError as e:
        error_msg = str(e)
        assert "demo.recipe" in error_msg
        assert "default" in error_msg
        # Error message no longer includes available_providers (security)
        # That info is now logged separately
        assert "demo.missing" in error_msg
        assert "demo.missing" in error_msg
    else:
        pytest.fail("Expected KeyError was not raised")
