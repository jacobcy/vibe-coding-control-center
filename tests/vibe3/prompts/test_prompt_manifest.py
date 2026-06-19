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
    """Regression test: kind:file sources pass through --prompt-file, not stdin.

    All kind:file sources (sections, variables, material_catalog) are assembled
    into the prompt body and written to a temp file passed via --prompt-file.
    The codeagent-wrapper stdin-mode threshold (~800 chars) only applies to the
    task positional argument, not the prompt file content.

    This test verifies that kind:file sources resolve to existing files on disk,
    preventing regressions where files are missing or paths are broken.
    """
    from vibe3.prompts.models import VariableSourceKind

    manifest = PromptManifest.load_default()

    missing: list[str] = []

    for recipe_key, recipe in manifest.recipes.items():
        # Check section_recipe sections
        if recipe.kind == "section_recipe" and recipe.loaded_definition:
            for variant_key, variant in recipe.loaded_definition.variants.items():
                for section in variant.sections:
                    if (
                        section.source
                        and section.source.kind == VariableSourceKind.FILE
                    ):
                        file_path = _resolve_repo_path(Path(section.source.path))
                        if not file_path.exists():
                            missing.append(
                                f"{recipe_key}/{variant_key}/{section.key}: "
                                f"{section.source.path} (file not found)"
                            )

        # Check template_recipe variables
        if recipe.kind == "template_recipe" and recipe.loaded_definition:
            for var_name, var_source in recipe.loaded_definition.variables.items():
                if var_source.kind == VariableSourceKind.FILE:
                    file_path = _resolve_repo_path(Path(var_source.path))
                    if not file_path.exists():
                        missing.append(
                            f"{recipe_key}/variable/{var_name}: "
                            f"{var_source.path} (file not found)"
                        )

        # Check template_recipe material_catalog
        if recipe.kind == "template_recipe" and recipe.loaded_definition:
            if recipe.loaded_definition.material_catalog:
                for material in recipe.loaded_definition.material_catalog:
                    if material.source.kind == VariableSourceKind.FILE:
                        file_path = _resolve_repo_path(Path(material.source.path))
                        if not file_path.exists():
                            missing.append(
                                f"{recipe_key}/material/{material.name}: "
                                f"{material.source.path} (file not found)"
                            )

    if missing:
        missing_list = "\n  - ".join([""] + missing)
        pytest.fail(f"kind:file sources point to non-existent files:{missing_list}")


def test_load_for_prompts_path_none_uses_default() -> None:
    """When prompts_path is None, load_for_prompts_path returns the default manifest."""
    manifest = PromptManifest.load_for_prompts_path(None)
    assert isinstance(manifest, PromptManifest)
    # Verify it loaded the default recipes (recipes from repo config exist)
    assert "plan.default" in manifest.recipes
    assert "review.default" in manifest.recipes
    assert "run.plan" in manifest.recipes


def test_load_for_prompts_path_custom_path(tmp_path: Path) -> None:
    """When prompts_path is set, loads from prompts_path.parent/prompt-recipes.yaml."""
    prompts_dir = tmp_path / "config" / "prompts"
    prompts_dir.mkdir(parents=True)
    recipes_path = prompts_dir / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  custom.recipe:
    variants:
      default:
        sections:
          - custom.section
""",
        encoding="utf-8",
    )

    # Simulate prompts_path as a file in the prompts dir (e.g. a .envrc or marker)
    prompts_file = prompts_dir / "some-file"
    prompts_file.touch()

    manifest = PromptManifest.load_for_prompts_path(prompts_file)
    assert "custom.recipe" in manifest.recipes
    assert manifest.recipe("custom.recipe").variant("default").sections == (
        "custom.section",
    )


def test_load_for_prompts_path_custom_path_with_manifest(tmp_path: Path) -> None:
    """Verify load_for_prompts_path works with a direct path to a prompts dir."""
    prompts_dir = tmp_path / "my-prompts"
    prompts_dir.mkdir(parents=True)
    recipes_path = prompts_dir / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  my.recipe:
    variants:
      default:
        sections:
          - my.section
""",
        encoding="utf-8",
    )

    # Simulate prompts_path pointing to a settings file in the prompts dir
    manifest = PromptManifest.load_for_prompts_path(prompts_dir / "custom-config.yaml")
    assert "my.recipe" in manifest.recipes


# Layer parsing and filtering tests


def test_parse_section_layer_from_yaml(tmp_path: Path) -> None:
    """Verify section layer field is correctly parsed from YAML."""
    from vibe3.prompts.models import MaterialLayer

    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  test.recipe:
    variants:
      default:
        sections:
          - key: test.core_section
            layer: core_invariant
          - key: test.policy_section
            layer: project_policy
          - key: test.no_layer_section
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)
    recipe = manifest.recipe("test.recipe")

    # Check loaded_definition has layer info
    assert recipe.loaded_definition is not None
    variant_spec = recipe.loaded_definition.variants["default"]
    assert len(variant_spec.sections) == 3

    assert variant_spec.sections[0].layer == MaterialLayer.CORE_INVARIANT
    assert variant_spec.sections[1].layer == MaterialLayer.PROJECT_POLICY
    assert variant_spec.sections[2].layer is None


def test_parse_material_catalog_layer_from_yaml(tmp_path: Path) -> None:
    """Verify material_catalog layer field is correctly parsed from YAML."""
    from vibe3.prompts.models import MaterialLayer

    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  test.recipe:
    kind: template_recipe
    template_key: test.template
    material_catalog:
      - name: test/material1.md
        source:
          kind: file
          path: test/material1.md
        layer: project_policy
      - name: test/material2.md
        source:
          kind: file
          path: test/material2.md
        layer: runtime_evidence
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)
    recipe = manifest.recipe("test.recipe")

    assert recipe.loaded_definition is not None
    assert len(recipe.loaded_definition.material_catalog) == 2

    assert (
        recipe.loaded_definition.material_catalog[0].layer
        == MaterialLayer.PROJECT_POLICY
    )
    assert (
        recipe.loaded_definition.material_catalog[1].layer
        == MaterialLayer.RUNTIME_EVIDENCE
    )


def test_render_sections_filters_by_active_layers(tmp_path: Path) -> None:
    """Verify render_sections filters out sections with inactive layers."""
    from vibe3.prompts.models import MaterialLayer

    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  test.recipe:
    variants:
      default:
        sections:
          - key: test.core
            layer: core_invariant
          - key: test.policy
            layer: project_policy
          - key: test.no_layer
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)

    # Cross-project: only core_invariant active, project_policy should be filtered
    active_layers = {MaterialLayer.CORE_INVARIANT, MaterialLayer.RUNTIME_EVIDENCE}
    rendered = manifest.render_sections(
        "test.recipe",
        "default",
        providers={
            "test.core": lambda: "Core content",
            "test.policy": lambda: "Policy content",
            "test.no_layer": lambda: "No layer content",
        },
        active_layers=active_layers,
    )

    # Should contain core and no_layer sections, but not policy
    assert "Core content" in rendered
    assert "No layer content" in rendered
    assert "Policy content" not in rendered


def test_render_sections_no_active_layers_allows_all(tmp_path: Path) -> None:
    """Verify active_layers=None renders all sections (backward compatible)."""

    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  test.recipe:
    variants:
      default:
        sections:
          - key: test.core
            layer: core_invariant
          - key: test.policy
            layer: project_policy
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)

    # active_layers=None should render all sections
    rendered = manifest.render_sections(
        "test.recipe",
        "default",
        providers={
            "test.core": lambda: "Core content",
            "test.policy": lambda: "Policy content",
        },
        active_layers=None,  # None means no filtering
    )

    assert "Core content" in rendered
    assert "Policy content" in rendered


def test_get_section_sources_respects_layer_enabled(tmp_path: Path) -> None:
    """Verify get_section_sources sets enabled field based on active_layers."""
    from vibe3.prompts.models import MaterialLayer

    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  test.recipe:
    variants:
      default:
        sections:
          - key: test.core
            layer: core_invariant
          - key: test.policy
            layer: project_policy
          - key: test.no_layer
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)

    # Cross-project: only core_invariant active
    active_layers = {MaterialLayer.CORE_INVARIANT, MaterialLayer.RUNTIME_EVIDENCE}
    sources = manifest.get_section_sources("test.recipe", "default", active_layers)

    assert len(sources) == 3
    assert sources[0].key == "test.core"
    assert sources[0].layer == MaterialLayer.CORE_INVARIANT
    assert sources[0].enabled is True

    assert sources[1].key == "test.policy"
    assert sources[1].layer == MaterialLayer.PROJECT_POLICY
    assert sources[1].enabled is False  # Not in active_layers

    assert sources[2].key == "test.no_layer"
    assert sources[2].layer is None
    assert sources[2].enabled is True  # No layer = always enabled


def test_default_layer_is_none(tmp_path: Path) -> None:
    """Verify sections without layer annotation have layer=None."""
    recipes_path = tmp_path / "prompt-recipes.yaml"
    recipes_path.write_text(
        """
recipes:
  test.recipe:
    variants:
      default:
        sections:
          - test.section_without_layer
""",
        encoding="utf-8",
    )

    manifest = PromptManifest.load(recipes_path)
    recipe = manifest.recipe("test.recipe")

    assert recipe.loaded_definition is not None
    variant_spec = recipe.loaded_definition.variants["default"]
    assert len(variant_spec.sections) == 1
    assert variant_spec.sections[0].layer is None
