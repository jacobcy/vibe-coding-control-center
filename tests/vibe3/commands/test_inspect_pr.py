"""Tests for vibe inspect pr subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services are mocked.
"""

import json
from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def _mock_change_analysis():
    return {
        "source_type": "pr",
        "identifier": "42",
        "impact": {"changed_files": ["a.py"]},
        "dag": {"impacted_modules": ["mod_a"]},
        "score": {"score": 3, "level": "LOW", "block": False, "risk_level": "LOW"},
    }


def test_inspect_pr_missing_arg_shows_error():
    """vibe inspect pr (缺少 PR 号) → 友好错误，非崩溃。"""
    result = runner.invoke(app, ["pr"])
    assert result.exit_code != 0
    assert "missing" in result.output.lower() or "error" in result.output.lower()


def test_inspect_pr_with_number():
    with patch(
        "vibe3.commands.inspect.build_change_analysis",
        return_value=_mock_change_analysis(),
    ):
        result = runner.invoke(app, ["pr", "42"])
    assert result.exit_code == 0
    assert "PR #42" in result.output


def test_inspect_pr_json():
    with patch(
        "vibe3.commands.inspect.build_change_analysis",
        return_value=_mock_change_analysis(),
    ):
        result = runner.invoke(app, ["pr", "42", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["identifier"] == "42"


def test_inspect_pr_help():
    result = runner.invoke(app, ["pr", "--help"])
    assert result.exit_code == 0
    assert "PR number" in result.output
