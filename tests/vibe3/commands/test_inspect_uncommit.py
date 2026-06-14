"""Tests for vibe inspect uncommit subcommand."""

from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def _mock_change_analysis():
    """Build a mock change analysis result."""
    return {
        "source_type": "uncommit",
        "identifier": "working-tree",
        "changed_files": ["test.py"],
        "changed_symbols": {"test.py": ["test_func"]},
        "impact": {"impacted_modules": ["test_module"]},
        "dag": {"impacted_modules": ["test_module"]},
        "score": {
            "score": 3,
            "level": "LOW",
            "block": False,
            "risk_level": "LOW",
        },
    }


def test_inspect_uncommit_default() -> None:
    with patch(
        "vibe3.commands.inspect_change.build_change_analysis",
        return_value=_mock_change_analysis(),
    ):
        result = runner.invoke(app, ["uncommit"])
    assert result.exit_code == 0
    assert "Uncommitted" in result.output or "working-tree" in result.output


def test_inspect_uncommit_json() -> None:
    with patch(
        "vibe3.commands.inspect_change.build_change_analysis",
        return_value=_mock_change_analysis(),
    ):
        result = runner.invoke(app, ["uncommit", "--json"])
    assert result.exit_code == 0
    # Deprecation warning mixed into stdout by CliRunner defaults
    assert "deprecated" in result.output.lower()
    assert '"source_type": "uncommit"' in result.output


def test_inspect_uncommit_help() -> None:
    result = runner.invoke(app, ["uncommit", "--help"])
    assert result.exit_code == 0
    assert "uncommitted" in result.output.lower()
