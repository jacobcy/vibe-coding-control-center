"""Tests for async-by-default CLI options."""

from typer.testing import CliRunner

from vibe3.cli import app as cli_app

runner = CliRunner(env={"NO_COLOR": "1"})


class TestAsyncDefaults:
    def test_run_help_shows_async_and_sync(self) -> None:
        result = runner.invoke(cli_app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--async" in result.output
        assert "[default: True]" in result.output or "[default: async]" in result.output

    def test_plan_help_shows_async_and_sync(self) -> None:
        result = runner.invoke(cli_app, ["plan", "task", "--help"])
        assert result.exit_code == 0
        assert "--async" in result.output
        assert "[default: True]" in result.output or "[default: async]" in result.output

    def test_review_help_shows_async_and_sync(self) -> None:
        result = runner.invoke(cli_app, ["review", "base", "--help"])
        assert result.exit_code == 0
        assert "--async" in result.output
        assert "[default: True]" in result.output or "[default: async]" in result.output
