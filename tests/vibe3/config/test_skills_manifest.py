"""Regression tests for cross-agent skill installation policy."""

from __future__ import annotations

import json
from pathlib import Path


def test_codex_manifest_installs_caveman_skill_family() -> None:
    """Codex setup should reproduce the Caveman skills available in Claude."""
    manifest = json.loads(Path("config/v3/skills.json").read_text(encoding="utf-8"))

    packages = {
        package["source"]: set(package["skills"])
        for package in manifest["global"]["packages"]
    }

    assert "codex" in manifest["global"]["agents"]
    assert packages["JuliusBrussee/caveman"] == {
        "cavecrew",
        "caveman",
        "caveman-commit",
        "caveman-compress",
        "caveman-help",
        "caveman-review",
        "caveman-stats",
    }
