# tests/vibe3/assets/test_sync.py
"""Tests for asset sync service."""

from pathlib import Path

from vibe3.assets.sync import AssetSync


def test_sync_copies_builtin_assets_to_global(tmp_path: Path) -> None:
    """Sync must copy builtin assets to global directory."""
    # Setup: create fake builtin source
    builtin_dir = tmp_path / "builtin"
    builtin_prompts = builtin_dir / "prompts" / "test.yaml"
    builtin_prompts.parent.mkdir(parents=True)
    builtin_prompts.write_text("builtin content")

    global_dir = tmp_path / "global"

    sync = AssetSync(
        builtin_dir=builtin_dir,
        global_dir=global_dir,
    )

    sync.run()

    # Verify: global copy exists
    global_copy = global_dir / "prompts" / "test.yaml"
    assert global_copy.exists()
    assert global_copy.read_text() == "builtin content"


def test_sync_skips_existing_identical_files(tmp_path: Path) -> None:
    """Sync must skip files with matching checksums."""
    builtin_dir = tmp_path / "builtin"
    builtin_prompts = builtin_dir / "prompts" / "test.yaml"
    builtin_prompts.parent.mkdir(parents=True)
    builtin_prompts.write_text("same content")

    global_dir = tmp_path / "global"
    global_prompts = global_dir / "prompts" / "test.yaml"
    global_prompts.parent.mkdir(parents=True, exist_ok=True)
    global_prompts.write_text("same content")

    sync = AssetSync(
        builtin_dir=builtin_dir,
        global_dir=global_dir,
    )

    result = sync.run()

    # Verify: skipped due to identical checksum
    assert result.copied == 0
    assert result.skipped == 1


def test_sync_overwrites_changed_files(tmp_path: Path) -> None:
    """Sync must overwrite files with different content."""
    builtin_dir = tmp_path / "builtin"
    builtin_prompts = builtin_dir / "prompts" / "test.yaml"
    builtin_prompts.parent.mkdir(parents=True)
    builtin_prompts.write_text("new content")

    global_dir = tmp_path / "global"
    global_prompts = global_dir / "prompts" / "test.yaml"
    global_prompts.parent.mkdir(parents=True, exist_ok=True)
    global_prompts.write_text("old content")

    sync = AssetSync(
        builtin_dir=builtin_dir,
        global_dir=global_dir,
    )

    result = sync.run()

    # Verify: overwritten with new content
    assert result.copied == 1
    assert global_prompts.read_text() == "new content"


def test_sync_handles_missing_builtin_dir(tmp_path: Path) -> None:
    """Sync must handle missing builtin directory gracefully."""
    builtin_dir = tmp_path / "builtin"  # Does not exist
    global_dir = tmp_path / "global"

    sync = AssetSync(
        builtin_dir=builtin_dir,
        global_dir=global_dir,
    )

    result = sync.run()

    # Verify: empty result, no crash
    assert result.copied == 0
    assert result.skipped == 0
    assert result.errors == []


def test_sync_generates_manifest(tmp_path: Path) -> None:
    """Sync must generate manifest.json with checksums."""
    builtin_dir = tmp_path / "builtin"
    builtin_prompts = builtin_dir / "prompts" / "test.yaml"
    builtin_prompts.parent.mkdir(parents=True)
    builtin_prompts.write_text("content")

    global_dir = tmp_path / "global"

    sync = AssetSync(
        builtin_dir=builtin_dir,
        global_dir=global_dir,
    )

    sync.run()

    # Verify: manifest.json exists
    manifest_path = global_dir / "manifest.json"
    assert manifest_path.exists()

    # Verify: manifest has correct structure
    from vibe3.assets.manifest import AssetManifest

    manifest = AssetManifest.load(manifest_path)
    assert manifest.version == "1.0.0"
    assert "prompts/test.yaml" in manifest.checksums


def test_sync_copies_nested_directories(tmp_path: Path) -> None:
    """Sync must handle nested directory structures."""
    builtin_dir = tmp_path / "builtin"
    builtin_file = builtin_dir / "prompts" / "nested" / "deep" / "test.yaml"
    builtin_file.parent.mkdir(parents=True)
    builtin_file.write_text("nested content")

    global_dir = tmp_path / "global"

    sync = AssetSync(
        builtin_dir=builtin_dir,
        global_dir=global_dir,
    )

    result = sync.run()

    # Verify: nested structure preserved
    global_file = global_dir / "prompts" / "nested" / "deep" / "test.yaml"
    assert global_file.exists()
    assert global_file.read_text() == "nested content"
    assert result.copied == 1


def test_sync_handles_copy_errors_gracefully(tmp_path: Path) -> None:
    """Sync must handle file copy errors gracefully."""
    import os
    import stat

    builtin_dir = tmp_path / "builtin"
    builtin_file = builtin_dir / "prompts" / "test.yaml"
    builtin_file.parent.mkdir(parents=True)
    builtin_file.write_text("content")

    global_dir = tmp_path / "global"

    # Create a read-only parent directory to trigger permission error
    global_prompts = global_dir / "prompts"
    global_prompts.mkdir(parents=True)
    os.chmod(global_prompts, stat.S_IRUSR | stat.S_IXUSR)  # read + execute only

    sync = AssetSync(
        builtin_dir=builtin_dir,
        global_dir=global_dir,
    )

    result = sync.run()

    # Verify: error is captured, not raised
    assert len(result.errors) == 1
    assert "prompts/test.yaml" in result.errors[0]

    # Cleanup: restore permissions
    os.chmod(global_prompts, stat.S_IRWXU)
