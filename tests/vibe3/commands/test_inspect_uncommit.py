"""Tests for vibe inspect uncommit subcommand."""

import json
from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def _mock_change_analysis():
    return {
        "source_type": "uncommit",
        "identifier": "working-tree",
        "impact": {"changed_files": ["a.py"]},
        "dag": {"impacted_modules": ["mod_a"]},
        "score": {"score": 3, "level": "LOW", "block": False, "risk_level": "LOW"},
    }


def test_inspect_uncommit_runs() -> None:
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
    data = json.loads(result.output)
    assert data["source_type"] == "uncommit"
    assert data["identifier"] == "working-tree"


def test_inspect_uncommit_help() -> None:
    result = runner.invoke(app, ["uncommit", "--help"])
    assert result.exit_code == 0
    assert "uncommitted" in result.output.lower()
