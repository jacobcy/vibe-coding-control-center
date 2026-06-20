"""Tests for cross-project material layer behavior.

Tests two scenarios:
- Scenario A: Running inside vibe-center repo (all layers active)
- Scenario B: Running cross-project (only core_invariant and runtime_evidence active)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from vibe3.prompts import PromptManifest
from vibe3.prompts.models import MaterialLayer


class TestSameRepoScenario:
    """Scenario A — Running inside vibe-center repo (all layers active)."""

    def test_all_layers_active_in_vibe_center(self, tmp_path: Path) -> None:
        """Verify all layers are active when running inside vibe-center."""
        from vibe3.prompts import detect_active_layers

        # Mock bundled_project_root to return current directory
        with patch(
            "vibe3.clients.runtime_assets.bundled_project_root",
            return_value=Path.cwd().resolve(),
        ):
            active_layers = detect_active_layers()

        assert MaterialLayer.CORE_INVARIANT in active_layers
        assert MaterialLayer.REPO_PROFILE in active_layers
        assert MaterialLayer.PROJECT_POLICY in active_layers
        assert MaterialLayer.RUNTIME_EVIDENCE in active_layers

    def test_plan_recipe_renders_all_sections_in_vibe_center(
        self, tmp_path: Path
    ) -> None:
        """Verify plan.default recipe renders all sections in vibe-center."""
        recipes_path = tmp_path / "prompt-recipes.yaml"
        recipes_path.write_text(
            """
recipes:
  plan.default:
    template_key: plan.default
    variants:
      first.bootstrap:
        sections:
          - key: plan.policy
            layer: core_invariant
          - key: common.rules
            layer: core_invariant
          - key: plan.output_format
            layer: core_invariant
          - key: plan.exit_contract
            layer: core_invariant
""",
            encoding="utf-8",
        )

        manifest = PromptManifest.load(recipes_path)

        # All layers active
        active_layers = {
            MaterialLayer.CORE_INVARIANT,
            MaterialLayer.REPO_PROFILE,
            MaterialLayer.PROJECT_POLICY,
            MaterialLayer.RUNTIME_EVIDENCE,
        }

        rendered = manifest.render_sections(
            "plan.default",
            "first.bootstrap",
            providers={
                "plan.policy": lambda: "Policy content",
                "common.rules": lambda: "Rules content",
                "plan.output_format": lambda: "Output format",
                "plan.exit_contract": lambda: "Exit contract",
            },
            active_layers=active_layers,
        )

        # All sections should be present
        assert "Policy content" in rendered
        assert "Rules content" in rendered
        assert "Output format" in rendered
        assert "Exit contract" in rendered

    def test_governance_material_catalog_all_included_in_vibe_center(
        self, tmp_path: Path
    ) -> None:
        """Verify governance.scan material_catalog all included in vibe-center."""
        recipes_path = tmp_path / "prompt-recipes.yaml"
        recipes_path.write_text(
            """
recipes:
  governance.scan:
    kind: template_recipe
    template_key: orchestra.governance.plan
    material_catalog:
      - name: supervisor/governance/assignee-pool.md
        source:
          kind: file
          path: supervisor/governance/assignee-pool.md
        layer: project_policy
      - name: supervisor/governance/roadmap-intake.md
        source:
          kind: file
          path: supervisor/governance/roadmap-intake.md
        layer: project_policy
""",
            encoding="utf-8",
        )

        manifest = PromptManifest.load(recipes_path)

        # All layers active
        active_layers = {
            MaterialLayer.CORE_INVARIANT,
            MaterialLayer.REPO_PROFILE,
            MaterialLayer.PROJECT_POLICY,
            MaterialLayer.RUNTIME_EVIDENCE,
        }

        sources = manifest.get_section_sources(
            "governance.scan", "", active_layers=active_layers
        )

        # All materials should be enabled
        assert all(s.enabled for s in sources)
        assert len(sources) == 2


class TestCrossProjectScenario:
    """Scenario B — Running cross-project (outside vibe-center)."""

    def test_only_core_and_runtime_active_cross_project(self, tmp_path: Path) -> None:
        """Verify only core_invariant and runtime_evidence active cross-project."""
        from vibe3.prompts import detect_active_layers

        # Mock bundled_project_root to return different path than CWD
        with patch(
            "vibe3.clients.runtime_assets.bundled_project_root",
            return_value=Path("/different/path/to/vibe-center"),
        ):
            active_layers = detect_active_layers()

        assert MaterialLayer.CORE_INVARIANT in active_layers
        assert MaterialLayer.RUNTIME_EVIDENCE in active_layers
        assert MaterialLayer.REPO_PROFILE not in active_layers
        assert MaterialLayer.PROJECT_POLICY not in active_layers

    def test_project_policy_sections_filtered_cross_project(
        self, tmp_path: Path
    ) -> None:
        """Verify project_policy sections are filtered in cross-project context."""
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
          - key: test.runtime
            layer: runtime_evidence
          - key: test.policy
            layer: project_policy
          - key: test.repo_profile
            layer: repo_profile
""",
            encoding="utf-8",
        )

        manifest = PromptManifest.load(recipes_path)

        # Cross-project: only core and runtime active
        active_layers = {MaterialLayer.CORE_INVARIANT, MaterialLayer.RUNTIME_EVIDENCE}

        rendered = manifest.render_sections(
            "test.recipe",
            "default",
            providers={
                "test.core": lambda: "Core content",
                "test.runtime": lambda: "Runtime content",
                "test.policy": lambda: "Policy content",
                "test.repo_profile": lambda: "Repo profile content",
            },
            active_layers=active_layers,
        )

        # Only core and runtime should be present
        assert "Core content" in rendered
        assert "Runtime content" in rendered
        assert "Policy content" not in rendered
        assert "Repo profile content" not in rendered

    def test_provenance_shows_policy_disabled_cross_project(
        self, tmp_path: Path
    ) -> None:
        """Verify project_policy sections disabled in cross-project."""
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

        # Cross-project: only core and runtime active
        active_layers = {MaterialLayer.CORE_INVARIANT, MaterialLayer.RUNTIME_EVIDENCE}

        sources = manifest.get_section_sources("test.recipe", "default", active_layers)

        assert len(sources) == 2

        # Core should be enabled
        assert sources[0].key == "test.core"
        assert sources[0].layer == MaterialLayer.CORE_INVARIANT
        assert sources[0].enabled is True

        # Policy should be disabled
        assert sources[1].key == "test.policy"
        assert sources[1].layer == MaterialLayer.PROJECT_POLICY
        assert sources[1].enabled is False

    def test_no_layer_sections_always_enabled(self, tmp_path: Path) -> None:
        """Verify sections without layer annotation are always enabled."""
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
          - key: test.no_layer
""",
            encoding="utf-8",
        )

        manifest = PromptManifest.load(recipes_path)

        # Cross-project: only core and runtime active
        active_layers = {MaterialLayer.CORE_INVARIANT, MaterialLayer.RUNTIME_EVIDENCE}

        sources = manifest.get_section_sources("test.recipe", "default", active_layers)

        assert len(sources) == 2

        # No-layer section should be enabled regardless of active_layers
        assert sources[1].key == "test.no_layer"
        assert sources[1].layer is None
        assert sources[1].enabled is True

    def test_render_sections_with_no_active_layers_allows_all(
        self, tmp_path: Path
    ) -> None:
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

        # None means no filtering (backward compatible)
        rendered = manifest.render_sections(
            "test.recipe",
            "default",
            providers={
                "test.core": lambda: "Core content",
                "test.policy": lambda: "Policy content",
            },
            active_layers=None,
        )

        # All sections should be present
        assert "Core content" in rendered
        assert "Policy content" in rendered


class TestCommonRulesIntegration:
    """Integration tests using real prompt-recipes.yaml for common.rules layer.

    After the common.md split:
    - common.rules = core_invariant (vibe toolchain guidance, available everywhere)
    - common-develop.rules = project_policy (vibe-center only)
    """

    REAL_RECIPES = (
        Path(__file__).resolve().parents[3] / "config/prompts/prompt-recipes.yaml"
    )

    ALL_LAYERS = {
        MaterialLayer.CORE_INVARIANT,
        MaterialLayer.REPO_PROFILE,
        MaterialLayer.PROJECT_POLICY,
        MaterialLayer.RUNTIME_EVIDENCE,
    }

    CROSS_PROJECT_LAYERS = {
        MaterialLayer.CORE_INVARIANT,
        MaterialLayer.RUNTIME_EVIDENCE,
    }

    RECIPES_WITH_COMMON_RULES = [
        ("run.plan", "coding.bootstrap"),
        ("run.plan", "retry.bootstrap"),
        ("plan.default", "first.bootstrap"),
        ("plan.default", "retry.bootstrap"),
        ("review.default", "first.bootstrap"),
        ("review.default", "retry.bootstrap"),
    ]

    def test_common_rules_tagged_as_core_invariant(self) -> None:
        """Verify common.rules is tagged core_invariant in all recipes."""
        manifest = PromptManifest.load(self.REAL_RECIPES)

        for recipe_key, variant_key in self.RECIPES_WITH_COMMON_RULES:
            sources = manifest.get_section_sources(
                recipe_key, variant_key, active_layers=self.ALL_LAYERS
            )
            common_rules = [s for s in sources if s.key == "common.rules"]
            tag = f"{recipe_key}/{variant_key}"
            assert (
                len(common_rules) == 1
            ), f"{tag}: want 1 common.rules, got {len(common_rules)}"
            assert (
                common_rules[0].layer == MaterialLayer.CORE_INVARIANT
            ), f"{tag}: should be core_invariant"

    def test_common_rules_enabled_everywhere(self) -> None:
        """Verify common.rules is enabled in both same-repo and cross-project."""
        manifest = PromptManifest.load(self.REAL_RECIPES)

        for recipe_key, variant_key in self.RECIPES_WITH_COMMON_RULES:
            tag = f"{recipe_key}/{variant_key}"

            all_sources = manifest.get_section_sources(
                recipe_key, variant_key, active_layers=self.ALL_LAYERS
            )
            common_rules = [s for s in all_sources if s.key == "common.rules"]
            assert (
                common_rules[0].enabled is True
            ), f"{tag}: should be enabled in vibe-center"

            cross_sources = manifest.get_section_sources(
                recipe_key, variant_key, active_layers=self.CROSS_PROJECT_LAYERS
            )
            cross_common = [s for s in cross_sources if s.key == "common.rules"]
            assert (
                cross_common[0].enabled is True
            ), f"{tag}: should be enabled cross-project"

    def test_common_develop_tagged_as_project_policy(self) -> None:
        """Verify common-develop.rules is tagged project_policy in all recipes."""
        manifest = PromptManifest.load(self.REAL_RECIPES)

        for recipe_key, variant_key in self.RECIPES_WITH_COMMON_RULES:
            sources = manifest.get_section_sources(
                recipe_key, variant_key, active_layers=self.ALL_LAYERS
            )
            develop = [s for s in sources if s.key == "common-develop.rules"]
            tag = f"{recipe_key}/{variant_key}"
            assert (
                len(develop) == 1
            ), f"{tag}: want 1 common-develop.rules, got {len(develop)}"
            assert (
                develop[0].layer == MaterialLayer.PROJECT_POLICY
            ), f"{tag}: should be project_policy"

    def test_common_develop_disabled_cross_project(self) -> None:
        """Verify common-develop.rules is disabled in cross-project context."""
        manifest = PromptManifest.load(self.REAL_RECIPES)

        for recipe_key, variant_key in self.RECIPES_WITH_COMMON_RULES:
            sources = manifest.get_section_sources(
                recipe_key, variant_key, active_layers=self.CROSS_PROJECT_LAYERS
            )
            develop = [s for s in sources if s.key == "common-develop.rules"]
            tag = f"{recipe_key}/{variant_key}"
            assert (
                develop[0].enabled is False
            ), f"{tag}: should be disabled cross-project"
