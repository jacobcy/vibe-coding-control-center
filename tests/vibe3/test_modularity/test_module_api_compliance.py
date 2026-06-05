"""Tests for module API encapsulation and boundary enforcement."""

from __future__ import annotations

import pytest

from .conftest import extract_cross_module_imports


class TestModuleAPICompliance:
    """Test that modules respect API boundaries defined by __all__."""

    @pytest.mark.xfail(
        reason="Known architectural debt: 897 cross-module imports bypass "
        "__all__ boundary (9 top-level not-in-__all__, 888 deep submodule imports)"
    )
    def test_module_api_compliance(
        self, module_registry: list[str], module_public_api: dict[str, set[str]]
    ) -> None:
        """Verify modules only import from other modules' public APIs (__all__).

        This test identifies two types of violations:
        1. Top-level imports of symbols not in __all__:
           from vibe3.X import Y where Y ∉ X.__all__
        2. Deep imports that bypass module boundary:
           from vibe3.X.submodule import Y

        Phase 1: Collect violations (xfail)
        Phase 2: Fix violations and remove xfail
        """
        violations = []

        for module_name in module_registry:
            for imp in extract_cross_module_imports(module_name):
                if imp.is_deep:
                    # Deep import: from vibe3.X.submodule import Y
                    # This bypasses the module boundary entirely
                    violations.append(
                        f"{imp.source_file}: deep import from {imp.import_path} "
                        f"(should use 'from vibe3.{imp.target_module} import ...') "
                    )
                else:
                    # Top-level import: from vibe3.X import Y
                    for symbol in imp.symbols:
                        # Check for private symbol imports
                        if symbol.startswith("_") and not symbol.startswith("__"):
                            violations.append(
                                f"{imp.source_file}: imports private symbol {symbol} "
                                f"from {imp.target_module}"
                            )
                        # Check for non-__all__ symbol imports
                        elif symbol not in module_public_api.get(
                            imp.target_module, set()
                        ):
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

                # Also check symbol-level private imports
                if not imp.is_deep:
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
