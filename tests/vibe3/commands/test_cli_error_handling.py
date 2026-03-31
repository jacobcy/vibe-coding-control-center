"""Tests for CLI top-level error handling behavior."""

from unittest.mock import patch

import pytest

from vibe3.exceptions import SystemError


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
