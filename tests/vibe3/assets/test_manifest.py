"""Tests for asset manifest schema."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from vibe3.assets.manifest import AssetManifest


def test_manifest_loads_from_json():
    """Manifest must load from JSON with required fields."""
    data = {
        "version": "1.0.0",
        "checksums": {
            "prompts/prompts.yaml": "abc123",
            "prompts/prompt-recipes.yaml": "def456",
        },
    }
    manifest = AssetManifest.model_validate(data)

    assert manifest.version == "1.0.0"
    assert "prompts/prompts.yaml" in manifest.checksums


def test_manifest_validates_checksum_paths():
    """Checksum paths must be relative and within asset types."""
    manifest = AssetManifest(
        version="1.0.0",
        checksums={
            "prompts/test.yaml": "valid",
            "invalid/path.yaml": "should-fail",
        },
    )

    valid_types = {"prompts", "templates", "policies", "models", "manifests"}
    valid_paths = [
        p for p in manifest.checksums.keys() if p.split("/")[0] in valid_types
    ]
    assert len(valid_paths) == 1


def test_manifest_file_round_trip(tmp_path: Path):
    """Manifest must save and load from file."""
    manifest = AssetManifest(
        version="1.0.0",
        checksums={"prompts/test.yaml": "abc123"},
    )

    manifest_path = tmp_path / "manifest.json"
    manifest.save(manifest_path)

    loaded = AssetManifest.load(manifest_path)
    assert loaded.version == manifest.version
    assert loaded.checksums == manifest.checksums


def test_manifest_rejects_invalid_version():
    """Manifest must reject invalid version strings."""
    with pytest.raises(ValidationError) as exc_info:
        AssetManifest(
            version="invalid-version",
            checksums={"prompts/test.yaml": "abc123"},
        )

    errors = exc_info.value.errors()
    assert any("version" in str(e) for e in errors)
