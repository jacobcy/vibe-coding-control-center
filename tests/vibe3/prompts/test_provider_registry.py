"""Tests for provider registry and builtin variable resolvers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from vibe3.prompts.exceptions import ProviderNotFoundError
from vibe3.prompts.models import PromptVariableSource, VariableSourceKind
from vibe3.prompts.provider_registry import ProviderRegistry


class TestProviderRegistry:
    def test_registry_starts_empty(self) -> None:
        registry = ProviderRegistry()
        assert registry.list_providers() == []

    def test_register_and_call_provider(self) -> None:
        registry = ProviderRegistry()

        def my_provider(context: dict) -> str:
            return "value_from_provider"

        registry.register("my_provider", my_provider)
        assert "my_provider" in registry.list_providers()
        assert registry.call("my_provider", {}) == "value_from_provider"

    def test_call_unknown_provider_raises(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            registry.call("nonexistent", {})

    def test_register_overwrites_existing(self) -> None:
        registry = ProviderRegistry()
        registry.register("p", lambda ctx: "first")
        registry.register("p", lambda ctx: "second")
        assert registry.call("p", {}) == "second"


class TestBuiltinResolvers:
    def test_resolve_literal(self) -> None:
        from vibe3.prompts.builtin_providers import resolve_source

        src = PromptVariableSource(kind=VariableSourceKind.LITERAL, value="hello world")
        result = resolve_source(src, runtime_context={}, registry=ProviderRegistry())
        assert result == "hello world"

    def test_resolve_literal_missing_value_returns_empty(self) -> None:
        from vibe3.prompts.builtin_providers import resolve_source

        src = PromptVariableSource(kind=VariableSourceKind.LITERAL, value=None)
        result = resolve_source(src, runtime_context={}, registry=ProviderRegistry())
        assert result == ""

    def test_resolve_file(self, tmp_path: Path) -> None:
        from vibe3.prompts.builtin_providers import resolve_source

        f = tmp_path / "content.txt"
        f.write_text("file content here", encoding="utf-8")
        src = PromptVariableSource(kind=VariableSourceKind.FILE, path=str(f))
        result = resolve_source(src, runtime_context={}, registry=ProviderRegistry())
        assert result == "file content here"

    def test_resolve_file_missing_returns_empty(self) -> None:
        from vibe3.prompts.builtin_providers import resolve_source

        src = PromptVariableSource(
            kind=VariableSourceKind.FILE, path="/nonexistent/file.txt"
        )
        result = resolve_source(src, runtime_context={}, registry=ProviderRegistry())
        assert result == ""

    def test_resolve_skill(self, tmp_path: Path) -> None:
        from vibe3.prompts.builtin_providers import resolve_source

        skill_file = tmp_path / "skills" / "vibe-test" / "SKILL.md"
        skill_file.parent.mkdir(parents=True)
        skill_file.write_text("# Test Skill", encoding="utf-8")

        src = PromptVariableSource(kind=VariableSourceKind.SKILL, skill="vibe-test")
        with patch(
            "vibe3.prompts.builtin_providers.find_skill_file",
            return_value=skill_file,
        ):
            result = resolve_source(
                src, runtime_context={}, registry=ProviderRegistry()
            )
        assert result == "# Test Skill"

    def test_resolve_skill_not_found_returns_empty(self) -> None:
        from vibe3.prompts.builtin_providers import resolve_source

        src = PromptVariableSource(
            kind=VariableSourceKind.SKILL, skill="nonexistent-skill"
        )
        with patch(
            "vibe3.prompts.builtin_providers.find_skill_file",
            return_value=None,
        ):
            result = resolve_source(
                src, runtime_context={}, registry=ProviderRegistry()
            )
        assert result == ""

    def test_resolve_command(self) -> None:
        from vibe3.prompts.builtin_providers import resolve_source

        src = PromptVariableSource(
            kind=VariableSourceKind.COMMAND, command="echo hello"
        )
        result = resolve_source(src, runtime_context={}, registry=ProviderRegistry())
        assert result.strip() == "hello"

    def test_resolve_command_failure_returns_empty(self) -> None:
        from vibe3.prompts.builtin_providers import resolve_source

        src = PromptVariableSource(
            kind=VariableSourceKind.COMMAND,
            command="false",  # always exits non-zero
        )
        result = resolve_source(src, runtime_context={}, registry=ProviderRegistry())
        assert result == ""

    def test_resolve_provider_delegates_to_registry(self) -> None:
        from vibe3.prompts.builtin_providers import resolve_source

        registry = ProviderRegistry()
        registry.register("my.provider", lambda ctx: "provider_value")
        src = PromptVariableSource(
            kind=VariableSourceKind.PROVIDER, provider="my.provider"
        )
        result = resolve_source(src, runtime_context={}, registry=registry)
        assert result == "provider_value"

    def test_resolve_provider_passes_context(self) -> None:
        from vibe3.prompts.builtin_providers import resolve_source

        registry = ProviderRegistry()
        received: list[dict] = []
        registry.register("ctx.provider", lambda ctx: received.append(ctx) or "ok")
        src = PromptVariableSource(
            kind=VariableSourceKind.PROVIDER, provider="ctx.provider"
        )
        resolve_source(src, runtime_context={"key": "val"}, registry=registry)
        assert received == [{"key": "val"}]
