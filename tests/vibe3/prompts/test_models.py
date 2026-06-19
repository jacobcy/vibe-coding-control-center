"""Tests for prompt recipe and provenance models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vibe3.prompts.exceptions import MissingVariableError
from vibe3.prompts.models import (
    AnomalyFlags,
    PromptRecipe,
    PromptRenderProvenance,
    PromptRenderResult,
    PromptVariableProvenance,
    PromptVariableSource,
    SectionSourceProvenance,
    VariableSourceKind,
)


class TestVariableSourceKind:
    def test_all_kinds_exist(self) -> None:
        kinds = {k.value for k in VariableSourceKind}
        assert kinds == {"literal", "skill", "file", "command", "provider"}


class TestPromptVariableSource:
    def test_literal_source(self) -> None:
        src = PromptVariableSource(kind=VariableSourceKind.LITERAL, value="hello")
        assert src.kind == VariableSourceKind.LITERAL
        assert src.value == "hello"

    def test_skill_source(self) -> None:
        src = PromptVariableSource(
            kind=VariableSourceKind.SKILL, skill="vibe-orchestra"
        )
        assert src.skill == "vibe-orchestra"

    def test_file_source(self) -> None:
        src = PromptVariableSource(
            kind=VariableSourceKind.FILE, path="config/prompts.yaml"
        )
        assert src.path == "config/prompts.yaml"

    def test_command_source(self) -> None:
        src = PromptVariableSource(
            kind=VariableSourceKind.COMMAND, command="git status"
        )
        assert src.command == "git status"

    def test_provider_source(self) -> None:
        src = PromptVariableSource(
            kind=VariableSourceKind.PROVIDER, provider="orchestra.snapshot"
        )
        assert src.provider == "orchestra.snapshot"


class TestPromptRecipe:
    def test_minimal_recipe(self) -> None:
        recipe = PromptRecipe(
            template_key="orchestra.governance.plan",
            variables={},
        )
        assert recipe.template_key == "orchestra.governance.plan"
        assert recipe.variables == {}

    def test_recipe_with_variables(self) -> None:
        recipe = PromptRecipe(
            template_key="orchestra.governance.plan",
            variables={
                "skill_content": PromptVariableSource(
                    kind=VariableSourceKind.SKILL, skill="vibe-orchestra"
                ),
                "server_status": PromptVariableSource(
                    kind=VariableSourceKind.LITERAL, value="running"
                ),
            },
        )
        assert "skill_content" in recipe.variables
        assert "server_status" in recipe.variables

    def test_recipe_is_immutable(self) -> None:
        recipe = PromptRecipe(
            template_key="test.template",
            variables={},
        )
        with pytest.raises((AttributeError, TypeError, ValidationError)):
            recipe.template_key = "other"  # type: ignore[misc]


class TestPromptVariableProvenance:
    def test_provenance_holds_source_info(self) -> None:
        prov = PromptVariableProvenance(
            variable="skill_content",
            source_kind=VariableSourceKind.SKILL,
            resolved_from="skills/vibe-orchestra/SKILL.md",
            value_preview="# Orchestra\n...",
        )
        assert prov.variable == "skill_content"
        assert prov.source_kind == VariableSourceKind.SKILL
        assert prov.resolved_from == "skills/vibe-orchestra/SKILL.md"

    def test_provenance_value_preview_truncates(self) -> None:
        long_value = "x" * 1000
        prov = PromptVariableProvenance(
            variable="v",
            source_kind=VariableSourceKind.LITERAL,
            resolved_from="literal",
            value_preview=long_value[:200],
        )
        assert len(prov.value_preview) <= 200


class TestPromptRenderResult:
    def test_render_result_holds_text_and_provenance(self) -> None:
        prov = PromptVariableProvenance(
            variable="v",
            source_kind=VariableSourceKind.LITERAL,
            resolved_from="literal",
            value_preview="val",
        )
        result = PromptRenderResult(
            recipe_key="test.key",
            template_source="config/prompts.yaml",
            rendered_text="Hello val",
            provenance=(prov,),
        )
        assert result.rendered_text == "Hello val"
        assert result.recipe_key == "test.key"
        assert len(result.provenance) == 1

    def test_render_result_is_immutable(self) -> None:
        result = PromptRenderResult(
            recipe_key="test.key",
            template_source="config/prompts.yaml",
            rendered_text="text",
            provenance=(),
        )
        with pytest.raises((AttributeError, TypeError, ValidationError)):
            result.rendered_text = "other"  # type: ignore[misc]


class TestPromptExceptions:
    def test_missing_variable_error(self) -> None:
        exc = MissingVariableError(variable="skill_content", template_key="test.key")
        assert "skill_content" in str(exc)
        assert "test.key" in str(exc)


class TestSectionSourceProvenance:
    def test_section_source_provenance_immutable(self) -> None:
        """Verify frozen model."""
        prov = SectionSourceProvenance(
            key="test_section",
            source_kind=VariableSourceKind.FILE,
            source_ref="config/test.md",
        )
        with pytest.raises((AttributeError, TypeError, ValidationError)):
            prov.key = "other"  # type: ignore[misc]

    def test_section_source_minimal(self) -> None:
        """Section source with only key."""
        prov = SectionSourceProvenance(key="header")
        assert prov.key == "header"
        assert prov.source_kind is None
        assert prov.source_ref is None


class TestPromptRenderProvenance:
    def test_prompt_render_provenance_immutable(self) -> None:
        """Verify frozen model."""
        prov = PromptRenderProvenance(
            recipe_key="test.recipe",
            variant_key="default",
        )
        with pytest.raises((AttributeError, TypeError, ValidationError)):
            prov.recipe_key = "other"  # type: ignore[misc]

    def test_prompt_render_provenance_defaults(self) -> None:
        """Verify default values."""
        prov = PromptRenderProvenance(
            recipe_key="test.recipe",
            variant_key="default",
        )
        assert prov.recipe_key == "test.recipe"
        assert prov.variant_key == "default"
        assert prov.section_order == ()
        assert prov.section_sources == ()
        assert prov.variable_provenance == ()
        assert prov.rendered_hash == ""
        assert prov.char_count == 0
        assert prov.token_estimate is None
        assert prov.warnings == ()
        assert isinstance(prov.anomalies, AnomalyFlags)


class TestAnomalyFlags:
    def test_anomaly_flags_defaults(self) -> None:
        """Verify all flags default to False."""
        flags = AnomalyFlags()
        assert flags.has_large_material is False
        assert flags.has_duplicate_material is False
        assert flags.missing_output_contract is False
        assert flags.missing_verification_contract is False
        assert flags.has_repo_profile is False
        assert flags.has_project_policy_overlay is False

    def test_anomaly_flags_immutable(self) -> None:
        """Verify frozen model."""
        flags = AnomalyFlags(has_large_material=True)
        with pytest.raises((AttributeError, TypeError, ValidationError)):
            flags.has_large_material = False  # type: ignore[misc]
