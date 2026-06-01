"""Tests to prevent architectural violations in the clients module."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestClientsModularity:
    """Test that clients module maintains architectural independence."""

    def test_clients_no_config_import(self) -> None:
        """Verify clients module does not import from vibe3.config.

        This test prevents architectural regression where clients (layer 6)
        imports from config (also layer 6 but should remain independent).

        Uses Python native implementation (no external dependencies).
        """
        import re

        clients_path = Path("src/vibe3/clients")

        if not clients_path.exists():
            pytest.skip("clients module not found")

        # Pattern matches both "from vibe3.config" and "import vibe3.config"
        pattern = re.compile(r"from vibe3\.config|import vibe3\.config")

        violations = []
        for py_file in clients_path.rglob("*.py"):
            content = py_file.read_text()
            match = pattern.search(content)
            if match:
                violations.append(
                    f"{py_file.relative_to(clients_path)}: {match.group()}"
                )

        if violations:
            pytest.fail(
                "clients module contains forbidden config imports:\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nclients module should not depend on config module. "
                "See issue #1682 for architectural context."
            )
