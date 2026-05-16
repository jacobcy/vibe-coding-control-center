"""Tests for assets command group."""

from pathlib import Path

from typer.testing import CliRunner

from vibe3.cli import app

runner = CliRunner()


def test_assets_sync_creates_global_directory(tmp_path: Path, monkeypatch):
    """Assets sync must create global directory."""
    # Setup: use temp directory as global assets
    global_dir = tmp_path / "global"
    monkeypatch.setenv("VIBE_ASSETS_DIR", str(global_dir))

    result = runner.invoke(app, ["assets", "sync"])

    assert result.exit_code == 0
    assert "Synced" in result.output or "Created" in result.output


def test_assets_status_shows_manifest_info(tmp_path: Path, monkeypatch):
    """Assets status must show manifest version and file count."""
    global_dir = tmp_path / "global"
    global_dir.mkdir(parents=True)

    # Create fake manifest
    import json

    manifest = {
        "version": "1.0.0",
        "checksums": {"prompts/test.yaml": "abc123"},
    }
    (global_dir / "manifest.json").write_text(json.dumps(manifest))

    monkeypatch.setenv("VIBE_ASSETS_DIR", str(global_dir))

    result = runner.invoke(app, ["assets", "status"])

    assert result.exit_code == 0
    assert "1.0.0" in result.output
    assert "│ Files" in result.output
    assert "│ 1" in result.output
