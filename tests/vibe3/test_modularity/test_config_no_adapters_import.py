"""Tests to prevent architectural violations in the config module."""

from __future__ import annotations

import re
from pathlib import Path

import pytest


class TestConfigModularity:
    def test_config_no_adapters_import(self) -> None:
        """Verify config module does not import from vibe3.adapters.

        Allows lazy imports inside functions (services-level wiring pattern).
        Only catches module-level imports that create hard dependencies.
        """
        config_path = Path("src/vibe3/config")
        # Pattern matches both "from vibe3.config" and "import vibe3.config"
        # We need to check if these are at module level (not inside functions)
        pattern = re.compile(
            r"^(?:from vibe3\.adapters|import vibe3\.adapters)", re.MULTILINE
        )
        violations = []
        for py_file in config_path.rglob("*.py"):
            content = py_file.read_text()
            match = pattern.search(content)
            if match:
                violations.append(
                    f"{py_file.relative_to(config_path)}: {match.group()}"
                )
        if violations:
            pytest.fail(
                "config module contains forbidden module-level adapters imports:\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nconfig module should not have hard dependencies on "
                "adapters module. Use dependency injection or lazy imports "
                "inside functions instead."
            )
