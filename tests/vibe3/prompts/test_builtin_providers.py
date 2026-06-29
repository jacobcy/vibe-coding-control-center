"""Tests for built-in prompt variable providers."""

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.prompts import builtin_providers
from vibe3.prompts.builtin_providers import resolve_skill_content


def test_relative_skill_uses_runtime_asset_resolution(
    monkeypatch, tmp_path: Path
) -> None:
    """Relative mechanism skills resolve independently of Git management root."""
    skill = tmp_path / "skills" / "example" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("content", encoding="utf-8")
    resolve_asset = MagicMock(return_value=skill)
    monkeypatch.setattr(builtin_providers, "resolve_runtime_asset", resolve_asset)

    content = resolve_skill_content("example", lambda _: "skills/example/SKILL.md")

    assert content == "content"
    resolve_asset.assert_called_once_with("skills/example/SKILL.md")


def test_missing_optional_skill_logs_actionable_warning(
    monkeypatch, tmp_path: Path
) -> None:
    """Missing optional skills retain None but expose the attempted location."""
    missing = tmp_path / "skills" / "missing" / "SKILL.md"
    bound_logger = MagicMock()
    monkeypatch.setattr(
        builtin_providers,
        "resolve_runtime_asset",
        MagicMock(return_value=missing),
    )
    monkeypatch.setattr(
        builtin_providers.logger,
        "bind",
        MagicMock(return_value=bound_logger),
    )

    content = resolve_skill_content("missing", lambda _: "skills/missing/SKILL.md")

    assert content is None
    builtin_providers.logger.bind.assert_called_once_with(
        domain="prompt_assembly",
        action="resolve_skill_content",
        skill="missing",
        cwd=str(Path.cwd()),
        resolved_path=str(missing),
    )
    bound_logger.warning.assert_called_once()
