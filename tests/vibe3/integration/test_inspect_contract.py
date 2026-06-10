"""Contract tests for inspect subcommands output format options.

Enforces that all inspect subcommands support --json and --yaml output.
Uses CliRunner for fast in-process validation; one subprocess smoke test
verifies the real CLI binary works end-to-end.

Reference: docs/v3/design/trace-inspect-output-format.md
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest
import yaml
from typer.testing import CliRunner

from vibe3.cli import app

if TYPE_CHECKING:
    pass

runner = CliRunner()

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
        assert "--json" in result.output, f"inspect {subcommand} missing --json"

    @pytest.mark.parametrize("subcommand", INSPECT_SUBCOMMANDS)
    def test_subcommand_has_yaml_option(self, subcommand: str) -> None:
        result = runner.invoke(app, ["inspect", subcommand, "--help"])
        assert "--yaml" in result.output, f"inspect {subcommand} missing --yaml"


class TestInspectYamlOutput:
    """Verify --yaml output is valid and has expected structure."""

    @pytest.mark.parametrize("subcommand", YAML_TESTABLE)
    def test_yaml_produces_valid_output(self, subcommand: str) -> None:
        args = YAML_ARGS.get(subcommand, [])
        result = runner.invoke(app, ["inspect", subcommand, *args, "--yaml"])
        assert result.exit_code == 0, f"inspect {subcommand} --yaml failed"
        data = yaml.safe_load(result.output)
        assert isinstance(data, dict), f"inspect {subcommand} YAML is not a dict"


@pytest.mark.integration
class TestInspectSubprocessSmoke:
    """One end-to-end subprocess test to verify the real CLI binary."""

    def test_dead_code_yaml_subprocess(self) -> None:
        """Verify dead-code --yaml works via real subprocess invocation."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "src/vibe3/cli.py",
                "inspect",
                "dead-code",
                "--yaml",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        data = yaml.safe_load(result.stdout)
        assert isinstance(data, dict)
        assert "total_symbols" in data
        assert "dead_code_count" in data
        assert "findings" in data
