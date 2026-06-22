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

    def test_clients_no_services_import(self) -> None:
        """Verify clients module does not import from vibe3.services.

        Clients are lower-level adapters/cache helpers. Importing the services
        barrel from clients creates an upward dependency and can perturb the
        lazy re-export graph used by mypy.
        """
        import re

        clients_path = Path("src/vibe3/clients")

        if not clients_path.exists():
            pytest.skip("clients module not found")

        pattern = re.compile(r"from vibe3\.services\b|import vibe3\.services\b")

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
                "clients module contains forbidden services imports:\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nclients module should not depend on the services layer. "
                "Pass service callbacks into clients instead."
            )

    def test_clients_no_exceptions_import(self) -> None:
        """Track clients/ imports from vibe3.exceptions barrel.

        L6 clients/ may legitimately depend on exception TYPES (GitError,
        GitHubError, etc.) defined directly in exceptions/__init__.py — these
        are L6 infrastructure. Lazy FUNCTION imports (classify_error_hybrid,
        get_error_handling_contract) through the barrel warrant review for
        dependency direction but are valid public API usage.

        Current baseline: 15 imports across clients/ (issue #2902).
        This is a growth-prevention gate, not a hard block.
        Increases over the baseline require justification.
        Do NOT resolve by replacing barrel imports with deep imports —
        public API is the contract.
        """
        import ast

        clients_path = Path("src/vibe3/clients")

        if not clients_path.exists():
            pytest.skip("clients module not found")

        # Use AST parsing to count barrel imports
        imports_found = []
        for py_file in clients_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue

            try:
                tree = ast.parse(py_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        if module == "vibe3.exceptions":
                            imported_names = ", ".join(
                                alias.name for alias in node.names
                            )
                            imports_found.append(
                                {
                                    "file": str(py_file.relative_to(clients_path)),
                                    "line": node.lineno,
                                    "import": f"from {module} import {imported_names}",
                                }
                            )
            except SyntaxError:
                continue

        # Baseline: 13 imports (reduced from 15 in issue #3085)
        # All are exception TYPE imports (GitError, GitHubError, etc.)
        # defined directly in exceptions/__init__.py — legitimate L6 deps.
        # Lazy FUNCTION imports (classify_error_hybrid, get_error_handling_contract)
        # have been eliminated via DI and inline severity inference.
        baseline = 13

        if imports_found:
            print(
                f"\n⚠️  Found {len(imports_found)} "
                f"exceptions barrel imports in clients/:"
            )
            for v in imports_found[:10]:
                print(f"   {v['file']}:{v['line']} - {v['import']}")
            if len(imports_found) > 10:
                print(f"   ... and {len(imports_found) - 10} more")

        # Hard gate: prevent growth beyond baseline
        assert len(imports_found) <= baseline, (
            f"Exceptions barrel imports in clients/ increased: "
            f"expected <= {baseline}, found {len(imports_found)}"
        )
