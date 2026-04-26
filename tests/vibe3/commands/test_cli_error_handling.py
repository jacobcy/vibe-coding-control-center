"""Tests for CLI top-level error handling behavior."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from vibe3.cli import app as cli_app
from vibe3.exceptions import SystemError

runner = CliRunner(env={"NO_COLOR": "1"})


def test_main_handles_system_error_without_traceback() -> None:
    """SystemError should be logged as concise message with exit code 2."""
    from vibe3 import cli

    with (
        patch.object(cli, "app", side_effect=SystemError("api failed")),
        patch.object(cli.logger, "error") as mock_error,
        patch.object(cli.logger, "exception") as mock_exception,
        pytest.raises(SystemExit) as exc_info,
    ):
        cli.main()

    assert exc_info.value.code == 2
    mock_error.assert_called_once_with("api failed")
    mock_exception.assert_not_called()


def test_run_show_prompt_is_exposed_and_forwarded() -> None:
    """Top-level vibe3 run should expose and forward --show-prompt."""
    with patch("vibe3.commands.run.run_command") as mock_run:
        result = runner.invoke(
            cli_app,
            ["run", "inspect prompt", "--dry-run", "--show-prompt", "--no-async"],
        )

    assert result.exit_code == 0
    assert mock_run.call_args.kwargs["dry_run"] is True
    assert mock_run.call_args.kwargs["show_prompt"] is True
    assert mock_run.call_args.kwargs["no_async"] is True
