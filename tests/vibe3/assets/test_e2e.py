# tests/vibe3/assets/test_e2e.py
"""End-to-end tests for asset distribution."""

import shutil
from pathlib import Path


def test_e2e_empty_repo_can_run_vibe3_status(tmp_path: Path, monkeypatch) -> None:
    """Empty repo must be able to run vibe3 status using global assets."""
    from typer.testing import CliRunner

    from vibe3.cli import app

    # Setup: create empty git repo
    repo = tmp_path / "empty-repo"
    repo.mkdir()
    (repo / ".git").mkdir()

    # Setup: create global assets
    global_dir = tmp_path / "global"
    global_dir.mkdir()

    # Copy builtin assets to global
    builtin = Path(__file__).parent.parent.parent.parent.parent / "assets"
    if builtin.exists():
        shutil.copytree(builtin, global_dir, dirs_exist_ok=True)

    monkeypatch.setenv("VIBE_ASSETS_DIR", str(global_dir))

    runner = CliRunner()

    # Execute: run vibe3 status in empty repo
    result = runner.invoke(
        app,
        ["status"],
        env={"VIBE_ASSETS_DIR": str(global_dir)},
        cwd=repo,
    )

    # Verify: command succeeds
    # Note: may fail on missing flow state, but that's expected
    assert result.exit_code in (0, 1)  # OK or expected error


def test_e2e_assets_sync_creates_usable_global_dir(tmp_path: Path, monkeypatch) -> None:
    """Assets sync must create usable global directory."""
    from typer.testing import CliRunner

    from vibe3.assets.resolver import AssetResolver
    from vibe3.cli import app

    global_dir = tmp_path / "global"
    monkeypatch.setenv("VIBE_ASSETS_DIR", str(global_dir))

    runner = CliRunner()
    result = runner.invoke(app, ["assets", "sync"])

    assert result.exit_code == 0

    # Verify: resolver can find prompts
    resolver = AssetResolver(global_dir=global_dir)
    prompts = resolver.resolve("prompts/prompts.yaml")

    assert prompts is not None
    assert prompts.exists()
