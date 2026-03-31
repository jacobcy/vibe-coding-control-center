"""Tests for the PromptAssembler."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.exceptions import MissingVariableError, TemplateNotFoundError
from vibe3.prompts.models import (
    PromptRecipe,
    PromptRenderResult,
    PromptVariableSource,
    VariableSourceKind,
)
from vibe3.prompts.provider_registry import ProviderRegistry


def _make_prompts_yaml(tmp_path: Path, templates: dict) -> Path:
    p = tmp_path / "prompts.yaml"
    p.write_text(yaml.dump(templates), encoding="utf-8")
    return p


class TestPromptAssemblerRender:
    def test_render_simple_literal_variables(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(
            tmp_path, {"greet": {"hello": "Hello {name}, welcome to {place}!"}}
        )
        recipe = PromptRecipe(
            template_key="greet.hello",
            variables={
                "name": PromptVariableSource(
                    kind=VariableSourceKind.LITERAL, value="Alice"
                ),
                "place": PromptVariableSource(
                    kind=VariableSourceKind.LITERAL, value="Vibe"
                ),
            },
        )
        assembler = PromptAssembler(prompts_path=prompts_path)
        result = assembler.render(recipe, runtime_context={})

        assert isinstance(result, PromptRenderResult)
        assert result.rendered_text == "Hello Alice, welcome to Vibe!"
        assert result.recipe_key == "greet.hello"

    def test_render_produces_provenance_for_each_variable(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {"t": {"k": "a={a} b={b}"}})
        recipe = PromptRecipe(
            template_key="t.k",
            variables={
                "a": PromptVariableSource(kind=VariableSourceKind.LITERAL, value="1"),
                "b": PromptVariableSource(kind=VariableSourceKind.LITERAL, value="2"),
            },
        )
        assembler = PromptAssembler(prompts_path=prompts_path)
        result = assembler.render(recipe, runtime_context={})

        var_names = {p.variable for p in result.provenance}
        assert "a" in var_names
        assert "b" in var_names

    def test_render_missing_template_key_raises(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {})
        recipe = PromptRecipe(template_key="no.such.key", variables={})
        assembler = PromptAssembler(prompts_path=prompts_path)
        with pytest.raises(TemplateNotFoundError):
            assembler.render(recipe, runtime_context={})

    def test_render_missing_variable_raises(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {"t": {"k": "Hello {name}!"}})
        recipe = PromptRecipe(
            template_key="t.k",
            variables={},  # no source for {name}
        )
        assembler = PromptAssembler(prompts_path=prompts_path)
        with pytest.raises(MissingVariableError) as exc_info:
            assembler.render(recipe, runtime_context={})
        assert exc_info.value.variable == "name"

    def test_render_with_provider_variable(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {"t": {"k": "Status: {status}"}})
        registry = ProviderRegistry()
        registry.register("get_status", lambda ctx: "running")
        recipe = PromptRecipe(
            template_key="t.k",
            variables={
                "status": PromptVariableSource(
                    kind=VariableSourceKind.PROVIDER, provider="get_status"
                ),
            },
        )
        assembler = PromptAssembler(prompts_path=prompts_path, registry=registry)
        result = assembler.render(recipe, runtime_context={})
        assert result.rendered_text == "Status: running"

    def test_render_with_file_variable(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {"t": {"k": "Content: {body}"}})
        content_file = tmp_path / "body.txt"
        content_file.write_text("file body", encoding="utf-8")
        recipe = PromptRecipe(
            template_key="t.k",
            variables={
                "body": PromptVariableSource(
                    kind=VariableSourceKind.FILE, path=str(content_file)
                ),
            },
        )
        assembler = PromptAssembler(prompts_path=prompts_path)
        result = assembler.render(recipe, runtime_context={})
        assert result.rendered_text == "Content: file body"

    def test_render_template_source_is_recorded(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {"t": {"k": "hi {x}"}})
        recipe = PromptRecipe(
            template_key="t.k",
            variables={
                "x": PromptVariableSource(kind=VariableSourceKind.LITERAL, value="y"),
            },
        )
        assembler = PromptAssembler(prompts_path=prompts_path)
        result = assembler.render(recipe, runtime_context={})
        assert str(prompts_path) in result.template_source

    def test_render_with_runtime_context_passed_to_provider(
        self, tmp_path: Path
    ) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {"t": {"k": "val={v}"}})
        registry = ProviderRegistry()
        received: list[dict] = []

        def cap(ctx: dict) -> str:
            received.append(dict(ctx))
            return "captured"

        registry.register("cap", cap)
        recipe = PromptRecipe(
            template_key="t.k",
            variables={
                "v": PromptVariableSource(
                    kind=VariableSourceKind.PROVIDER, provider="cap"
                ),
            },
        )
        assembler = PromptAssembler(prompts_path=prompts_path, registry=registry)
        assembler.render(recipe, runtime_context={"key": "ctx_val"})
        assert received == [{"key": "ctx_val"}]
