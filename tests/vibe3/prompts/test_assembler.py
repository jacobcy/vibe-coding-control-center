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


class TestGovernanceMaterialOverlay:
    """Test governance material auto-appends project-specific overlay."""

    def test_governance_material_with_overlay(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Test governance material auto-appends .vibe/governance overlay."""
        from vibe3.prompts.builtin_providers import _resolve_file

        # Create base governance material
        base_dir = tmp_path / "supervisor" / "governance"
        base_dir.mkdir(parents=True)
        base_file = base_dir / "roadmap-intake.md"
        base_file.write_text(
            "# Base Content\n\nThis is the default governance material.",
            encoding="utf-8",
        )

        # Create project-specific overlay
        vibe_dir = tmp_path / ".vibe" / "governance"
        vibe_dir.mkdir(parents=True)
        overlay_file = vibe_dir / "roadmap-intake.md"
        overlay_file.write_text(
            "\n# Project-Specific Extensions\n\nThis is project-specific content.",
            encoding="utf-8",
        )

        # Mock resolve_runtime_asset to use tmp_path
        def mock_resolve(path: str) -> Path:
            return tmp_path / path

        import vibe3.prompts.builtin_providers as module

        monkeypatch.setattr(module, "resolve_runtime_asset", mock_resolve)

        # Test resolution
        src = PromptVariableSource(
            kind=VariableSourceKind.FILE, path="supervisor/governance/roadmap-intake.md"
        )
        result = _resolve_file(src)

        # Verify both base and overlay content are present
        assert "# Base Content" in result
        assert "# Project-Specific Extensions" in result
        assert "default governance material" in result
        assert "project-specific content" in result

    def test_governance_material_no_overlay(self, tmp_path: Path, monkeypatch) -> None:
        """Test governance material works without project overlay."""
        from vibe3.prompts.builtin_providers import _resolve_file

        # Create only base governance material (no overlay)
        base_dir = tmp_path / "supervisor" / "governance"
        base_dir.mkdir(parents=True)
        base_file = base_dir / "assignee-pool.md"
        base_file.write_text("# Base Content Only", encoding="utf-8")

        # Mock resolve_runtime_asset to use tmp_path
        def mock_resolve(path: str) -> Path:
            return tmp_path / path

        import vibe3.prompts.builtin_providers as module

        monkeypatch.setattr(module, "resolve_runtime_asset", mock_resolve)

        # Test resolution
        src = PromptVariableSource(
            kind=VariableSourceKind.FILE, path="supervisor/governance/assignee-pool.md"
        )
        result = _resolve_file(src)

        # Should only have base content
        assert "# Base Content Only" in result
        assert ".vibe" not in result

    def test_non_governance_file_unchanged(self, tmp_path: Path, monkeypatch) -> None:
        """Test non-governance files are not affected by overlay logic."""
        from vibe3.prompts.builtin_providers import _resolve_file

        # Create a regular file (not governance material)
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test Content", encoding="utf-8")

        # Mock resolve_runtime_asset to use tmp_path
        def mock_resolve(path: str) -> Path:
            return tmp_path / path

        import vibe3.prompts.builtin_providers as module

        monkeypatch.setattr(module, "resolve_runtime_asset", mock_resolve)

        # Test resolution
        src = PromptVariableSource(kind=VariableSourceKind.FILE, path="test.md")
        result = _resolve_file(src)

        # Should only have original content (no overlay attempt)
        assert "# Test Content" in result
        assert len(result.split("\n\n")) == 1  # No overlay appended
