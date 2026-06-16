"""Contract tests for inspect subcommands output format options.

Enforces that all inspect subcommands support --json and --yaml output.
Uses CliRunner for fast in-process validation; one subprocess smoke test
verifies the real CLI binary works end-to-end.

Reference: docs/v3/design/trace-inspect-output-format.md
"""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

import pytest
import yaml
from typer.testing import CliRunner

from vibe3.cli import app

if TYPE_CHECKING:
    pass

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_RE.sub("", text)


# All inspect subcommands that should support both --json and --yaml.
INSPECT_SUBCOMMANDS = [
    "files",
    "symbols",
    "base",
    "uncommit",
    "commands",
    "dead-code",
]

# Subcommands that produce valid YAML output (skip base/uncommit in CI
# because they need git context that may not be available).
YAML_TESTABLE = [
    "files",
    "symbols",
    "commands",
    "dead-code",
]

# Args for each subcommand's --yaml invocation.
YAML_ARGS: dict[str, list[str]] = {
    "files": ["src/vibe3/cli.py"],
    "symbols": ["src/vibe3/cli.py"],
    "commands": [],
    "dead-code": [],
}


class TestInspectFormatContract:
    """Verify all inspect subcommands support --json and --yaml."""

    @pytest.mark.parametrize("subcommand", INSPECT_SUBCOMMANDS)
    def test_subcommand_has_json_option(self, subcommand: str) -> None:
        result = runner.invoke(app, ["inspect", subcommand, "--help"])
        output = _strip_ansi(result.output)
        assert "--json" in output, f"inspect {subcommand} missing --json"

    @pytest.mark.parametrize("subcommand", INSPECT_SUBCOMMANDS)
    def test_subcommand_has_yaml_option(self, subcommand: str) -> None:
        result = runner.invoke(app, ["inspect", subcommand, "--help"])
        output = _strip_ansi(result.output)
        assert "--yaml" in output, f"inspect {subcommand} missing --yaml"


class TestInspectYamlOutput:
    """Verify --yaml output is valid and has expected structure."""

    @pytest.mark.parametrize("subcommand", YAML_TESTABLE)
    def test_yaml_produces_valid_output(self, subcommand: str) -> None:
        args = YAML_ARGS.get(subcommand, [])
        result = runner.invoke(app, ["inspect", subcommand, *args, "--yaml"])
        assert result.exit_code == 0, f"inspect {subcommand} --yaml failed"
        # Use stdout only (stderr contains log messages)
        clean_output = _strip_ansi(result.stdout)
        data = yaml.safe_load(clean_output)
        assert isinstance(data, dict), f"inspect {subcommand} YAML is not a dict"


@pytest.mark.integration
class TestInspectSubprocessSmoke:
    """One end-to-end subprocess test to verify the real CLI binary."""

    def test_files_yaml_subprocess(self) -> None:
        """Verify files --yaml works via real subprocess invocation."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "src/vibe3/cli.py",
                "inspect",
                "files",
                "src/vibe3/cli.py",
                "--yaml",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        data = yaml.safe_load(result.stdout)
        assert isinstance(data, dict)
        assert "file" in data or "function_count" in data
