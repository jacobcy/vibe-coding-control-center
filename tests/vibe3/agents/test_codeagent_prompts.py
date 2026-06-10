"""Tests for prompt file preparation and content integrity."""

from __future__ import annotations

from vibe3.agents.codeagent_prompts import (
    build_prompt_file_content,
    prepare_prompt_file,
)


class TestBuildPromptFileContent:
    """Verify prompt content construction."""

    def test_passes_through_when_no_notice(self):
        result = build_prompt_file_content("hello", include_global_notice=False)
        assert result == "hello"

    def test_prepends_notice_when_configured(self, monkeypatch):
        monkeypatch.setattr(
            "vibe3.agents.codeagent_prompts.get_vibe_config",
            lambda: type(
                "Cfg",
                (),
                {"agent_prompt": type("AP", (), {"global_notice": " NOTICE "})()},
            )(),
        )
        result = build_prompt_file_content("body")
        assert result.startswith("NOTICE\n\n---\n\n")
        assert result.endswith("body")

    def test_skips_empty_notice(self, monkeypatch):
        monkeypatch.setattr(
            "vibe3.agents.codeagent_prompts.get_vibe_config",
            lambda: type(
                "Cfg", (), {"agent_prompt": type("AP", (), {"global_notice": "  "})()}
            )(),
        )
        result = build_prompt_file_content("body")
        assert result == "body"


class TestPreparePromptFile:
    """Verify prompt file creation and content integrity."""

    def test_file_created_and_readable(self, monkeypatch):
        monkeypatch.setattr(
            "vibe3.agents.codeagent_prompts.get_vibe_config",
            lambda: type(
                "Cfg", (), {"agent_prompt": type("AP", (), {"global_notice": ""})()}
            )(),
        )
        prompt = "# Test Prompt\nContent here"
        file_path, content = prepare_prompt_file(prompt)

        assert file_path.exists()
        assert file_path.suffix == ".md"
        assert file_path.read_text(encoding="utf-8") == content
        assert content == prompt

        file_path.unlink()

    def test_large_prompt_roundtrip(self, monkeypatch):
        monkeypatch.setattr(
            "vibe3.agents.codeagent_prompts.get_vibe_config",
            lambda: type(
                "Cfg", (), {"agent_prompt": type("AP", (), {"global_notice": ""})()}
            )(),
        )
        # 50KB prompt with governance-like content
        large_content = "# Governance Material\n" + ("x" * 50_000)
        file_path, content = prepare_prompt_file(large_content)

        file_size = file_path.stat().st_size
        assert file_size >= 50_000
        assert file_path.read_text(encoding="utf-8") == large_content
        assert content == large_content

        file_path.unlink()

    def test_unicode_content_preserved(self, monkeypatch):
        monkeypatch.setattr(
            "vibe3.agents.codeagent_prompts.get_vibe_config",
            lambda: type(
                "Cfg", (), {"agent_prompt": type("AP", (), {"global_notice": ""})()}
            )(),
        )
        prompt = "# 中文治理材料\n\n日文: あいう\nEmoji: ✅ ❌"
        file_path, content = prepare_prompt_file(prompt)

        assert file_path.read_text(encoding="utf-8") == prompt
        assert "中文治理材料" in content

        file_path.unlink()

    def test_file_written_to_codeagent_dir(self, monkeypatch):
        monkeypatch.setattr(
            "vibe3.agents.codeagent_prompts.get_vibe_config",
            lambda: type(
                "Cfg", (), {"agent_prompt": type("AP", (), {"global_notice": ""})()}
            )(),
        )
        file_path, _ = prepare_prompt_file("test")
        assert ".codeagent" in str(file_path)
        assert "agents" in str(file_path)

        file_path.unlink()
