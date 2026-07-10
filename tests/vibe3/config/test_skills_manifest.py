"""Regression tests for cross-agent skill installation policy."""

from __future__ import annotations

import json
from pathlib import Path


def test_codex_manifest_uses_plugin_backed_skills() -> None:
    """Codex primary skills should not be installed through npx skills."""
    manifest = json.loads(Path("config/v3/skills.json").read_text(encoding="utf-8"))

    assert manifest["global"]["agents"] == []
    assert manifest["global"]["packages"] == []
    assert set(manifest["project"]["agents"]) == {"codex", "claude-code"}
