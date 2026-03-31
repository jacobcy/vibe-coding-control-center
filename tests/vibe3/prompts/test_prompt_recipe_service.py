"""Tests for PromptRecipeService."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vibe3.prompts.exceptions import TemplateNotFoundError
from vibe3.prompts.models import PromptRecipe, PromptVariableSource, VariableSourceKind
from vibe3.prompts.provider_registry import ProviderRegistry
from vibe3.prompts.recipe_service import PromptRecipeService


def _make_prompts_yaml(tmp_path: Path, templates: dict) -> Path:
    p = tmp_path / "prompts.yaml"
    p.write_text(yaml.dump(templates), encoding="utf-8")
    return p


class TestPromptRecipeService:
    def test_render_with_inline_recipe(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {"greet": "Hello {name}!"})
        recipe = PromptRecipe(
            template_key="greet",
            variables={
                "name": PromptVariableSource(
                    kind=VariableSourceKind.LITERAL, value="World"
                )
            },
        )
        service = PromptRecipeService(prompts_path=prompts_path)
        result = service.render(recipe, runtime_context={})
        assert result.rendered_text == "Hello World!"

    def test_render_missing_template_raises(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {})
        recipe = PromptRecipe(template_key="no.key", variables={})
        service = PromptRecipeService(prompts_path=prompts_path)
        with pytest.raises(TemplateNotFoundError):
            service.render(recipe, runtime_context={})

    def test_render_with_provider_via_service(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {"status": "server={s}"})
        registry = ProviderRegistry()
        registry.register("get_s", lambda ctx: "up")
        recipe = PromptRecipe(
            template_key="status",
            variables={
                "s": PromptVariableSource(
                    kind=VariableSourceKind.PROVIDER, provider="get_s"
                )
            },
        )
        service = PromptRecipeService(prompts_path=prompts_path, registry=registry)
        result = service.render(recipe, runtime_context={})
        assert result.rendered_text == "server=up"

    def test_dry_run_summary_contains_key_info(self, tmp_path: Path) -> None:
        prompts_path = _make_prompts_yaml(tmp_path, {"greet": "Hi {x}!"})
        recipe = PromptRecipe(
            template_key="greet",
            variables={
                "x": PromptVariableSource(kind=VariableSourceKind.LITERAL, value="test")
            },
        )
        service = PromptRecipeService(prompts_path=prompts_path)
        summary = service.dry_run_summary(recipe, runtime_context={})
        assert "greet" in summary
        assert "Hi test!" in summary
