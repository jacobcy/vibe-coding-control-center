"""Tests to prevent architectural violations in the clients module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


class TestClientsModularity:
    """Test that clients module maintains architectural independence."""

    def test_clients_no_config_import(self) -> None:
        """Verify clients module does not import from vibe3.config.

        This test prevents architectural regression where clients (layer 6)
        imports from config (also layer 6 but should remain independent).

        Uses ripgrep (rg) to scan for forbidden imports:
        - Exit code 0: matches found (test should fail)
        - Exit code 1: no matches (test should pass)
        """
        clients_path = Path("src/vibe3/clients")

        if not clients_path.exists():
            pytest.skip("clients module not found")

        # Use ripgrep to search for config imports
        # Pattern matches both "from vibe3.config" and "import vibe3.config"
        result = subprocess.run(
            ["rg", "from vibe3\\.config|import vibe3\\.config", str(clients_path)],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Found forbidden imports - fail with details
            pytest.fail(
                "clients module contains forbidden config imports:\n"
                f"{result.stdout}\n"
                "clients module should not depend on config module. "
                "See issue #1682 for architectural context."
            )
        elif result.returncode == 1:
            # No matches found - test passes
            pass
        else:
            # rg error (exit code > 1)
            pytest.fail(
                f"ripgrep search failed with exit code {result.returncode}:\n"
                f"{result.stderr}"
            )
