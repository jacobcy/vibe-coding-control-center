"""Tests for prompt recipe and provenance models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vibe3.prompts.exceptions import MissingVariableError, UnusedVariableError
from vibe3.prompts.models import (
    PromptRecipe,
    PromptRenderResult,
    PromptVariableProvenance,
    PromptVariableSource,
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

    def test_unused_variable_error(self) -> None:
        exc = UnusedVariableError(variable="extra_var", template_key="test.key")
        assert "extra_var" in str(exc)
        assert "test.key" in str(exc)
