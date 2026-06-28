"""CLI contract tests for inspect files."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from vibe3.commands.inspect import app

runner = CliRunner()


def test_inspect_files_requires_explicit_path() -> None:
    result = runner.invoke(app, ["files"])

    assert result.exit_code != 0


def test_inspect_files_json_contains_only_single_file_ast_evidence() -> None:
    with patch(
        "vibe3.clients.GitClient.get_worktree_root",
        return_value=str(Path.cwd()),
    ):
        result = runner.invoke(
            app,
            ["files", "src/vibe3/commands/inspect_base.py", "--json"],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["status"] == "ready"
    assert payload["file"]["content_sha256"]
    assert payload["declarations"]
    assert "imported_by" not in payload
    assert "dependencies" not in payload


def test_inspect_files_directory_is_structured_unsupported() -> None:
    with patch(
        "vibe3.clients.GitClient.get_worktree_root",
        return_value=str(Path.cwd()),
    ):
        result = runner.invoke(app, ["files", "src/vibe3/commands", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "unsupported", result.output
    assert payload["diagnostics"][0]["code"] == "directory_not_supported"


def test_inspect_files_help_describes_single_python_file() -> None:
    result = runner.invoke(app, ["files", "--help"])

    assert result.exit_code == 0
    assert "single Python file" in result.output
