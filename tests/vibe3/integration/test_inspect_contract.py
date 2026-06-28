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
]


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
