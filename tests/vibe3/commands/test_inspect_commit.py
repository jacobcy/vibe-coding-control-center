"""Tests for vibe inspect commit subcommand.

Tests CLI surface: argument validation, help output, exit codes.
All external services are mocked.
"""

from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.clients.git_status_ops import _get_commit_files
from vibe3.commands.inspect import app

runner = CliRunner()


def _mock_change_analysis():
    return {
        "source_type": "commit",
        "identifier": "abc123",
        "impact": {"changed_files": ["a.py"]},
        "dag": {"impacted_modules": ["mod_a"]},
        "score": {"score": 3, "level": "LOW", "block": False, "risk_level": "LOW"},
    }


def test_inspect_commit_missing_arg_shows_error():
    result = runner.invoke(app, ["commit"])
    assert result.exit_code != 0
    assert "missing" in result.output.lower() or "error" in result.output.lower()


def test_inspect_commit_with_sha():
    mock = _mock_change_analysis()
    with patch(
        "vibe3.commands.inspect_change.build_change_analysis",
        return_value=mock,
    ):
        result = runner.invoke(app, ["commit", "abc123"])
    assert result.exit_code == 0
    assert "abc123" in result.output


def test__get_commit_files_merge_commit_with_duplicates():
    def mock_run(cmd):
        return """file1.py
file2.py
file1.py
file3.py
file2.py
"""

    result = _get_commit_files(mock_run, "abc123")
    assert result == ["file1.py", "file2.py", "file3.py"]
    assert len(result) == 3


def test__get_commit_files_regular_commit_no_duplicates():
    def mock_run(cmd):
        return """file1.py
file2.py
file3.py
"""

    result = _get_commit_files(mock_run, "abc123")
    assert result == ["file1.py", "file2.py", "file3.py"]
    assert len(result) == 3


def test__get_commit_files_empty_output():
    def mock_run(cmd):
        return ""

    result = _get_commit_files(mock_run, "abc123")
    assert result == []


def test__get_commit_files_whitespace_only_lines():
    def mock_run(cmd):
        return """file1.py

file2.py

file3.py
"""

    result = _get_commit_files(mock_run, "abc123")
    assert result == ["file1.py", "file2.py", "file3.py"]
