"""Tests for async-by-default CLI options."""

import re

from typer.testing import CliRunner

from vibe3.cli import app as cli_app

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestAsyncDefaults:
    def test_run_help_shows_async_and_sync(self) -> None:
        result = runner.invoke(cli_app, ["run", "--help"])
        output = strip_ansi(result.output)
        assert result.exit_code == 0
        assert "async" in output
        assert "sync" in output
        # Typer shows --no-async flag (inverted boolean)
        assert "--no-async" in output

    def test_plan_help_shows_async_and_sync(self) -> None:
        result = runner.invoke(cli_app, ["plan", "issue", "--help"])
        output = strip_ansi(result.output)
        assert result.exit_code == 0
        assert "async" in output
        assert "sync" in output
        # Typer shows --no-async flag (inverted boolean)
        assert "--no-async" in output

    def test_review_help_shows_async_and_sync(self) -> None:
        result = runner.invoke(cli_app, ["review", "base", "--help"])
        output = strip_ansi(result.output)
        assert result.exit_code == 0
        assert "async" in output
        assert "sync" in output
        # Typer shows --no-async flag (inverted boolean)
        assert "--no-async" in output
