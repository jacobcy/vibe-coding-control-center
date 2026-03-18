"""Tests for vibe review analyze-commit subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services (Codex, GitHub, Git) are mocked.
"""

from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.commands.review import app

runner = CliRunner()


def test_review_analyze_commit_missing_arg():
    result = runner.invoke(app, ["analyze-commit"])
    assert result.exit_code != 0
    assert "missing" in result.output.lower() or "error" in result.output.lower()


def test_review_analyze_commit_human():
    mock_result = {
        "lines_changed": 72,
        "files_changed": 5,
        "complexity_score": 5,
        "should_review": True,
    }
    with patch(
        "vibe3.services.commit_analyzer.analyze_commit",
        return_value=mock_result,
    ):
        result = runner.invoke(app, ["analyze-commit", "HEAD"])
    assert result.exit_code == 0
    assert "72" in result.output
    assert "5/10" in result.output


def test_review_analyze_commit_json():
    with patch(
        "vibe3.services.commit_analyzer.analyze_commit_json",
        return_value='{"lines_changed":72}',
    ):
        result = runner.invoke(app, ["analyze-commit", "HEAD", "--json"])
    assert result.exit_code == 0
    assert "lines_changed" in result.output
