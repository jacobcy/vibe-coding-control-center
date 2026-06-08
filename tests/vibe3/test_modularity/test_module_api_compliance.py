"""Tests for module API encapsulation and boundary enforcement."""

from __future__ import annotations

import pytest

from .conftest import extract_cross_module_imports


class TestModuleAPICompliance:
    """Test that modules respect API boundaries defined by __all__."""

    def test_module_api_compliance(
        self, module_registry: list[str], module_public_api: dict[str, set[str]]
    ) -> None:
        """Verify modules only import from other modules' public APIs (__all__).

        This test checks every cross-module import against the target top-level
        module's public API, regardless of whether the import uses a deep
        submodule path:

           from vibe3.X[.submodule] import Y where Y ∉ vibe3.X.__all__
        """
        violations = []

        for module_name in module_registry:
            for imp in extract_cross_module_imports(module_name):
                for symbol in imp.symbols:
                    # Check for private symbol imports
                    if symbol.startswith("_") and not symbol.startswith("__"):
                        violations.append(
                            f"{imp.source_file}: imports private symbol {symbol} "
                            f"from {imp.target_module}"
                        )
                    # Check for non-__all__ symbol imports
                    elif symbol not in module_public_api.get(imp.target_module, set()):
                        violations.append(
                            f"{imp.source_file}: imports {symbol} from "
                            f"{imp.target_module} (not in __all__)"
                        )

        if violations:
            pytest.fail(
                f"Module API violations ({len(violations)} found):\n"
                + "\n".join(f"  - {v}" for v in violations)
            )

    def test_no_private_submodule_access(self, module_registry: list[str]) -> None:
        """Verify no module imports from private submodules of other modules.

        This is a hard gate: accessing _private submodules across module
        boundaries is never acceptable.
        """
        violations = []

        for module_name in module_registry:
            for imp in extract_cross_module_imports(module_name):
                # Check if import path contains a private submodule segment
                parts = imp.import_path.split(".")
                for part in parts[2:]:  # Skip 'vibe3' and module name
                    if part.startswith("_") and not part.startswith("__"):
                        violations.append(
                            f"{imp.source_file}: imports from private submodule "
                            f"{imp.import_path}"
                        )
                        break

                # Also check symbol-level private imports. This applies to both
                # top-level imports and deep imports from public submodules.
                for symbol in imp.symbols:
                    if symbol.startswith("_") and not symbol.startswith("__"):
                        violations.append(
                            f"{imp.source_file}: imports private symbol "
                            f"{symbol} from {imp.target_module}"
                        )

        if violations:
            pytest.fail(
                "Private submodule/symbol access violations:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )

    @pytest.mark.xfail(
        reason="Enforcing top-level imports only (222 violations tracked in #2414)"
    )
    def test_no_deep_imports(self, module_registry: list[str]) -> None:
        """Verify all cross-module imports go through top-level module __init__.py.

        This enforces that consumers use the public API (via __all__) rather than
        bypassing it with deep imports like:
            from vibe3.X.submodule import Y  # Bad: bypasses __init__.py
        instead of:
            from vibe3.X import Y  # Good: uses public API
        """
        from .conftest import extract_cross_module_imports

        violations = []

        for module_name in module_registry:
            for imp in extract_cross_module_imports(module_name):
                # Check for deep imports (bypassing top-level __init__.py)
                if imp.is_deep:
                    violations.append(
                        f"{imp.source_file}: deep import {imp.import_path} "
                        f"(should use: from vibe3.{imp.target_module} import ...)"
                    )

        if violations:
            pytest.fail(
                f"Deep import violations ({len(violations)} found):\n"
                + "\n".join(f"  - {v}" for v in violations[:50])  # Show first 50
                + (
                    f"\n  ... and {len(violations) - 50} more"
                    if len(violations) > 50
                    else ""
                )
            )
