"""Tests for async-by-default CLI options."""

import re

from typer.testing import CliRunner

from vibe3.cli import app as cli_app
from vibe3.execution.codeagent_support import build_self_invocation

runner = CliRunner(env={"NO_COLOR": "1"})


def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


class TestAsyncDefaults:
    def test_run_help_shows_async_and_sync(self) -> None:
        result = runner.invoke(cli_app, ["run", "--help"])
        output = strip_ansi(result.stdout)
        assert result.exit_code == 0
        assert "async" in output
        assert "sync" in output
        # Typer shows --no-async flag (inverted boolean)
        assert "--no-async" in output

    def test_plan_help_shows_async_and_sync(self) -> None:
        result = runner.invoke(cli_app, ["plan", "issue", "--help"])
        output = strip_ansi(result.stdout)
        assert result.exit_code == 0
        assert "async" in output
        assert "sync" in output
        # Typer shows --no-async flag (inverted boolean)
        assert "--no-async" in output

    def test_review_help_shows_async_and_sync(self) -> None:
        result = runner.invoke(cli_app, ["review", "base", "--help"])
        output = strip_ansi(result.stdout)
        assert result.exit_code == 0
        assert "async" in output
        assert "sync" in output
        # Typer shows --no-async flag (inverted boolean)
        assert "--no-async" in output

    def test_build_self_invocation_appends_no_async_for_tmux_child(self) -> None:
        """Verify that self-invocation logic correctly standardizes on --no-async."""
        cmd = build_self_invocation(["run", "--plan", "/tmp/demo.md"])

        assert "--no-async" in cmd
        assert "--sync" not in cmd
        assert "--async" not in cmd

    def test_build_self_invocation_drops_legacy_async_and_standardizes(self) -> None:
        """Verify that legacy --async flag is dropped and standardized to --no-async."""
        cmd = build_self_invocation(["review", "base", "--async"])

        assert "--async" not in cmd
        assert "--no-async" in cmd
