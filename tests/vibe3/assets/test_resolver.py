"""Tests for asset resolver with layered lookup."""

from pathlib import Path

from vibe3.assets.resolver import AssetResolver


def test_resolver_returns_repo_local_when_exists(tmp_path: Path):
    """Resolver must prioritize repo-local path."""
    # Setup: create repo-local file
    repo_local = tmp_path / "prompts" / "test.yaml"
    repo_local.parent.mkdir(parents=True)
    repo_local.write_text("repo-local content")

    # Create global file (should be ignored)
    global_dir = tmp_path / "global"
    global_file = global_dir / "prompts" / "test.yaml"
    global_file.parent.mkdir(parents=True, exist_ok=True)
    global_file.write_text("global content")

    resolver = AssetResolver(global_dir=global_dir)
    result = resolver.resolve("prompts/test.yaml", repo_root=tmp_path)

    assert result == repo_local
    assert result.read_text() == "repo-local content"


def test_resolver_falls_back_to_global_when_no_repo_local(tmp_path: Path):
    """Resolver must fall back to global assets."""
    global_dir = tmp_path / "global"
    global_file = global_dir / "prompts" / "test.yaml"
    global_file.parent.mkdir(parents=True, exist_ok=True)
    global_file.write_text("global content")

    resolver = AssetResolver(global_dir=global_dir)
    result = resolver.resolve("prompts/test.yaml", repo_root=tmp_path)

    assert result == global_file
    assert result.read_text() == "global content"


def test_resolver_returns_none_when_not_found(tmp_path: Path):
    """Resolver must return None when asset not found in any layer."""
    resolver = AssetResolver(global_dir=tmp_path / "global")
    result = resolver.resolve("nonexistent.yaml", repo_root=tmp_path)

    assert result is None


def test_resolver_provenance_tracking(tmp_path: Path):
    """Resolver must track which layer provided the asset."""
    global_dir = tmp_path / "global"
    global_file = global_dir / "prompts" / "test.yaml"
    global_file.parent.mkdir(parents=True, exist_ok=True)
    global_file.write_text("global")

    resolver = AssetResolver(global_dir=global_dir)
    path, provenance = resolver.resolve_with_provenance(
        "prompts/test.yaml", repo_root=tmp_path
    )

    assert path == global_file
    assert provenance == "global"
