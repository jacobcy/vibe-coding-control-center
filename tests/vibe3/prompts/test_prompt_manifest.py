"""Tests for prompt recipe manifests."""

from pathlib import Path

import pytest

from vibe3.exceptions import MissingResourceError
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
    assert DEFAULT_PROMPT_RECIPES_PATH == Path("config/prompts/prompt-recipes.yaml")

    resolved = _resolve_repo_path(DEFAULT_PROMPT_RECIPES_PATH)

    assert resolved.name == "prompt-recipes.yaml"
    assert resolved.parts[-3:] == ("config", "prompts", "prompt-recipes.yaml")


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
    """Verify MissingResourceError when recipes file is missing."""
    missing_path = tmp_path / "missing-recipes.yaml"

    with pytest.raises(MissingResourceError) as exc_info:
        PromptManifest.load(missing_path)

    error = exc_info.value
    assert error.diagnostic.resource_type == "prompt-recipes"
    assert "Searched paths:" in error.message
    assert "Suggested fix:" in error.message


def test_prompt_manifest_raises_on_missing_recipe(tmp_path: Path) -> None:
    """Verify MissingResourceError when recipe key is not found."""
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

    with pytest.raises(MissingResourceError) as exc_info:
        manifest.recipe("missing.recipe")

    error = exc_info.value
    assert error.diagnostic.resource_type == "prompt-recipe-key"
    assert "missing.recipe" in error.resource
    assert "Suggested fix:" in error.message


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


def test_prompt_manifest_loads_section_recipe_with_section_sources(
    tmp_path: Path,
) -> None:
    """Verify section_recipe can have section-level source declarations."""
    from vibe3.prompts.models import VariableSourceKind

    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  manager.default:
    kind: section_recipe
    variants:
      first.bootstrap:
        sections:
          - key: manager.supervisor_content
            source:
              kind: file
              path: supervisor/manager.md
          - key: manager.target
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)
    recipe = manifest.recipe("manager.default")

    assert recipe.kind == "section_recipe"
    # Access loaded definition for full section specs
    assert recipe.loaded_definition is not None
    loaded_variant = recipe.loaded_definition.variants["first.bootstrap"]
    assert loaded_variant.sections[0].key == "manager.supervisor_content"
    assert loaded_variant.sections[0].source is not None
    assert loaded_variant.sections[0].source.kind == VariableSourceKind.FILE


def test_prompt_manifest_loads_template_recipe(tmp_path: Path) -> None:
    """Verify template_recipe kind with variables mapping."""
    from vibe3.prompts.models import VariableSourceKind

    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  governance.scan:
    kind: template_recipe
    template_key: orchestra.governance.plan
    variables:
      supervisor_content:
        kind: file
        path: supervisor/governance/assignee-pool.md
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)
    recipe = manifest.recipe("governance.scan")

    assert recipe.kind == "template_recipe"
    assert recipe.template_key == "orchestra.governance.plan"
    # Access loaded_definition for variables
    assert recipe.loaded_definition is not None
    vars = recipe.loaded_definition.variables
    assert vars["supervisor_content"].kind == VariableSourceKind.FILE


def test_no_large_file_sources_in_default_recipes() -> None:
    """Regression test: no recipe section with kind:file should reference large files.

    Large files (>2048 bytes) should use kind:literal with Read instruction instead
    to avoid codeagent-wrapper stdin-mode threshold (~800 chars).

    This prevents regressions where runtime centralization accidentally reverts
    the kind:literal fix (as happened in commit 44d26faf).
    """
    from vibe3.prompts.models import VariableSourceKind

    # 2048 bytes is a conservative upper bound for kind:file sources.
    # The runtime stdin-mode threshold is ~800 chars (CODEAGENT_STDIN_MODE_THRESHOLD).
    # Files between 801-2047 chars will pass this regression test but may still
    # trigger stdin mode at runtime; the recipe design should prefer kind:literal
    # for files approaching either threshold.
    max_file_size_bytes = 2048

    manifest = PromptManifest.load_default()

    violations: list[str] = []

    # Check all recipes in the manifest
    for recipe_key, recipe in manifest.recipes.items():

        # Check section_recipe sections
        if recipe.kind == "section_recipe" and recipe.loaded_definition:
            for variant_key, variant in recipe.loaded_definition.variants.items():
                for section in variant.sections:
                    if (
                        section.source
                        and section.source.kind == VariableSourceKind.FILE
                    ):
                        # Resolve the file path
                        file_path = _resolve_repo_path(Path(section.source.path))
                        if file_path.exists():
                            file_size = file_path.stat().st_size
                            if file_size > max_file_size_bytes:
                                violations.append(
                                    f"{recipe_key}/{variant_key}/{section.key}: "
                                    f"{section.source.path} is {file_size} bytes "
                                    f"(limit: {max_file_size_bytes})"
                                )

        # Check template_recipe variables
        if recipe.kind == "template_recipe" and recipe.loaded_definition:
            for var_name, var_source in recipe.loaded_definition.variables.items():
                if var_source.kind == VariableSourceKind.FILE:
                    # Resolve the file path
                    file_path = _resolve_repo_path(Path(var_source.path))
                    if file_path.exists():
                        file_size = file_path.stat().st_size
                        if file_size > max_file_size_bytes:
                            violations.append(
                                f"{recipe_key}/variable/{var_name}: "
                                f"{var_source.path} is {file_size} bytes "
                                f"(limit: {max_file_size_bytes})"
                            )

        # Check template_recipe material_catalog
        # Note: material_catalog entries are intentionally excluded from the 2KB
        # limit check. They are loaded via --prompt-file in the backend (not stdin),
        # so the codeagent-wrapper stdin-mode threshold does not apply.
        # Governance materials (assignee-pool.md ~45KB, etc.) must use kind:file
        # for direct disk loading (ADR-0003: no process-level caching).
        if False:  # pragma: no cover — material_catalog exempt from 2KB limit
            if recipe.kind == "template_recipe" and recipe.loaded_definition:
                if recipe.loaded_definition.material_catalog:
                    for material in recipe.loaded_definition.material_catalog:
                        if material.source.kind == VariableSourceKind.FILE:
                            # Resolve the file path
                            file_path = _resolve_repo_path(Path(material.source.path))
                            if file_path.exists():
                                file_size = file_path.stat().st_size
                                if file_size > max_file_size_bytes:
                                    violations.append(
                                        f"{recipe_key}/material/{material.name}: "
                                        f"{material.source.path} is {file_size} bytes "
                                        f"(limit: {max_file_size_bytes})"
                                    )

    if violations:
        violation_list = "\n  - ".join([""] + violations)
        pytest.fail(
            f"Found large file sources with kind:file (should use kind:literal):"
            f"{violation_list}"
        )
