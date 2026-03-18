"""Integration tests for vibe hooks CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vibe3.commands.hooks import app

runner = CliRunner()


def test_hooks_no_args_shows_help():
    """vibe hooks (无子命令) → shows help (exit 0 or 2 per typer no_args_is_help)."""
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output or "install" in result.output.lower()


def test_hooks_help_flag():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "install-hooks" in result.output
    assert "uninstall-hooks" in result.output


def test_install_hooks_success(tmp_path):
    source = tmp_path / "scripts" / "hooks" / "post-commit"
    source.parent.mkdir(parents=True)
    source.write_text("#!/bin/bash\necho hi")

    git_hooks = tmp_path / ".git" / "hooks"
    git_hooks.mkdir(parents=True)

    with (
        patch("vibe3.commands.hooks._ROOT", tmp_path),
        patch("os.access", return_value=True),
    ):
        result = runner.invoke(app, ["install-hooks"])

    assert result.exit_code == 0
    assert "Installed" in result.output
    assert (git_hooks / "post-commit").exists()


def test_install_hooks_source_missing(tmp_path):
    """source 文件不存在时应抛出 HookManagerError，exit 非 0。"""
    git_hooks = tmp_path / ".git" / "hooks"
    git_hooks.mkdir(parents=True)

    with patch("vibe3.commands.hooks._ROOT", tmp_path):
        result = runner.invoke(app, ["install-hooks"])

    assert result.exit_code != 0


def test_uninstall_hooks_exists(tmp_path):
    target = tmp_path / ".git" / "hooks" / "post-commit"
    target.parent.mkdir(parents=True)
    target.write_text("#!/bin/bash")

    with patch("vibe3.commands.hooks._ROOT", tmp_path):
        result = runner.invoke(app, ["uninstall-hooks"])

    assert result.exit_code == 0
    assert not target.exists()


def test_uninstall_hooks_not_exists(tmp_path):
    """hook 不存在时静默跳过，exit 0。"""
    (tmp_path / ".git" / "hooks").mkdir(parents=True)

    with patch("vibe3.commands.hooks._ROOT", tmp_path):
        result = runner.invoke(app, ["uninstall-hooks"])

    assert result.exit_code == 0
