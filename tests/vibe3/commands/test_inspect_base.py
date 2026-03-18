"""Tests for vibe inspect base subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services are mocked.
"""

from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def _mock_change_analysis():
    return {
        "source_type": "branch",
        "identifier": "feature/my-branch",
        "impact": {"changed_files": ["a.py"]},
        "dag": {"impacted_modules": ["mod_a"]},
        "score": {"score": 3, "level": "LOW", "block": False, "risk_level": "LOW"},
    }


def test_inspect_base_missing_arg_shows_error():
    result = runner.invoke(app, ["base"])
    assert result.exit_code != 0
    assert "missing" in result.output.lower() or "error" in result.output.lower()


def test_inspect_base_with_branch():
    mock = _mock_change_analysis()
    with patch(
        "vibe3.commands.inspect.build_change_analysis",
        return_value=mock,
    ):
        result = runner.invoke(app, ["base", "feature/my-branch"])
    assert result.exit_code == 0
    assert "feature/my-branch" in result.output
