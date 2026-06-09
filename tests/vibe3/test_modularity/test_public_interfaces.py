"""Tests for public API completeness."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass


def _is_legitimate_export(obj: object) -> tuple[bool, str]:
    """Check if a non-callable export follows a known legitimate pattern.

    Returns (is_ok, pattern_name) so the caller can include the reason
    in diagnostic messages.
    """
    obj_type = type(obj)

    # Dataclass singletons (domain role definitions, sync specs)
    if hasattr(obj_type, "__dataclass_fields__"):
        return True, "dataclass instance"

    # Pydantic model instances (configuration objects)
    try:
        from pydantic import BaseModel

        if isinstance(obj, BaseModel):
            return True, "pydantic model instance"
    except ImportError:
        pass

    # Module re-exports (barrel exports)
    import types

    if isinstance(obj, types.ModuleType):
        return True, "module re-export"

    # Primitive containers (set/frozenset used for config values)
    if isinstance(obj, (set, frozenset)):
        return True, "primitive container"

    # Path instances
    from pathlib import PurePath

    if isinstance(obj, PurePath):
        return True, "path instance"

    # Regex pattern
    import re

    if isinstance(obj, re.Pattern):
        return True, "regex pattern"

    # Type annotations (UnionType, etc.)
    if isinstance(obj, type):
        return True, "type annotation"

    # UnionType (e.g. str | None) — not a type subclass, but a type annotation
    import types as pytypes

    if isinstance(obj, pytypes.UnionType):
        return True, "union type annotation"

    return False, "unmatched"


# Truly unique non-callable exports that don't fit any pattern above.
# Each entry requires a justification comment — prefer refactoring to a
# callable (factory/classmethod) over adding entries here.
_DOCUMENTED_EXCEPTIONS: dict[str, str] = {
    "vibe3.ui.console": "Rich Console singleton — pre-configured for the project",
}


class TestModuleExports:
    """Test that modules properly define and export public interfaces."""

    def test_all_modules_have_all_defined(self, module_registry: list[str]) -> None:
        """Verify all modules have __all__ defined in __init__.py.

        This test intentionally FAILS for modules without __all__,
        surfacing them as follow-up work items.
        """
        modules_without_all = []

        for module_name in module_registry:
            init_path = Path(f"src/vibe3/{module_name}/__init__.py")
            if not init_path.exists():
                continue

            try:
                source = init_path.read_text(encoding="utf-8")
                tree = ast.parse(source)

                has_all = False
                for node in ast.walk(tree):
                    # Check for regular assignment: __all__ = [...]
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == "__all__":
                                has_all = True
                                break
                    # Check for annotated assignment: __all__: list[str] = [...]
                    elif isinstance(node, ast.AnnAssign):
                        if (
                            isinstance(node.target, ast.Name)
                            and node.target.id == "__all__"
                        ):
                            has_all = True

                if not has_all:
                    modules_without_all.append(module_name)

            except (SyntaxError, OSError) as e:
                modules_without_all.append(f"{module_name} (error: {e})")

        if modules_without_all:
            pytest.fail(
                "Modules without __all__ defined:\n"
                + "\n".join(f"  - {m}" for m in modules_without_all)
                + "\n\nThese modules need to define __all__ to "
                "specify their public API."
            )

    def test_all_exports_are_importable(self, module_registry: list[str]) -> None:
        """Verify that all names in __all__ are actually importable."""
        failures = []

        for module_name in module_registry:
            init_path = Path(f"src/vibe3/{module_name}/__init__.py")
            if not init_path.exists():
                continue

            try:
                # Try to import the module
                full_module_name = f"vibe3.{module_name}"
                module = importlib.import_module(full_module_name)

                # Check if __all__ exists
                if not hasattr(module, "__all__"):
                    # Skip if no __all__ (covered by test_all_modules_have_all_defined)
                    continue

                all_names = module.__all__

                # Verify each name is accessible
                for name in all_names:
                    if not hasattr(module, name):
                        failures.append(f"{full_module_name}.{name} not accessible")
                    elif getattr(module, name) is None:
                        failures.append(f"{full_module_name}.{name} is None")

            except ImportError as e:
                failures.append(f"{module_name}: import failed - {e}")
            except Exception as e:
                failures.append(f"{module_name}: unexpected error - {e}")

        if failures:
            pytest.fail(
                "Exports not importable:\n" + "\n".join(f"  - {f}" for f in failures)
            )

    def test_all_exports_are_callable_or_type(self, module_registry: list[str]) -> None:
        """Verify that exports are callable (function/class) or follow known patterns.

        Legitimate non-callable patterns:
        - Dataclass singletons (domain role definitions, sync specs)
        - Pydantic model instances (configuration objects)
        - Module re-exports (barrel exports within the same package)
        - Primitive containers (set, frozenset for config values)
        - Path / regex pattern instances
        - Type annotations (UnionType)
        """
        failures = []

        for module_name in module_registry:
            init_path = Path(f"src/vibe3/{module_name}/__init__.py")
            if not init_path.exists():
                continue

            try:
                full_module_name = f"vibe3.{module_name}"
                module = importlib.import_module(full_module_name)

                if not hasattr(module, "__all__"):
                    continue

                all_names = module.__all__

                for name in all_names:
                    obj = getattr(module, name, None)
                    if obj is None:
                        continue

                    if callable(obj):
                        continue

                    if isinstance(obj, (str, int, float, bool, dict, list, tuple)):
                        continue

                    is_ok, _reason = _is_legitimate_export(obj)
                    if is_ok:
                        continue

                    # Check documented exceptions (must have justification)
                    if f"{full_module_name}.{name}" in _DOCUMENTED_EXCEPTIONS:
                        continue

                    failures.append(
                        f"{full_module_name}.{name} is {type(obj).__name__} "
                        f"(no matching export pattern; "
                        f"consider a factory function or adding to a service layer)"
                    )

            except ImportError as e:
                failures.append(f"{module_name}: import failed - {e}")
            except Exception as e:
                failures.append(f"{module_name}: unexpected error - {e}")

        if failures:
            pytest.fail(
                "Non-standard exports found:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )

    def test_no_missing_exports(self, module_registry: list[str]) -> None:
        """Verify __all__ includes all symbols imported in __init__.py."""
        failures = []

        for module_name in module_registry:
            init_path = Path(f"src/vibe3/{module_name}/__init__.py")
            if not init_path.exists():
                continue

            try:
                source = init_path.read_text(encoding="utf-8")
                tree = ast.parse(source)

                # Extract names from __all__ if present
                all_names = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id == "__all__":
                                if isinstance(node.value, ast.List):
                                    for elt in node.value.elts:
                                        if isinstance(elt, ast.Constant):
                                            all_names.add(elt.value)

                # If no __all__, skip (covered by test_all_modules_have_all_defined)
                if not all_names:
                    continue

                # Extract imports from __init__.py
                imported_names = set()
                for node in tree.body:
                    if isinstance(node, ast.ImportFrom):
                        # Top-level imports
                        if node.module and node.module.startswith(
                            f"vibe3.{module_name}"
                        ):
                            for alias in node.names:
                                name = alias.asname or alias.name
                                if not name.startswith("_"):
                                    imported_names.add(name)
                        elif node.level and node.level > 0:
                            for alias in node.names:
                                name = alias.asname or alias.name
                                if not name.startswith("_"):
                                    imported_names.add(name)
                    elif isinstance(node, ast.If):
                        # Imports inside TYPE_CHECKING guards
                        for sub_node in node.body:
                            if isinstance(sub_node, ast.ImportFrom):
                                if sub_node.module and sub_node.module.startswith(
                                    f"vibe3.{module_name}"
                                ):
                                    for alias in sub_node.names:
                                        name = alias.asname or alias.name
                                        if not name.startswith("_"):
                                            imported_names.add(name)
                                elif sub_node.level and sub_node.level > 0:
                                    for alias in sub_node.names:
                                        name = alias.asname or alias.name
                                        if not name.startswith("_"):
                                            imported_names.add(name)

                # Check for missing exports
                missing = imported_names - all_names
                if missing:
                    failures.append(
                        f"{module_name}: missing from __all__: {sorted(missing)}"
                    )

            except (SyntaxError, OSError) as e:
                failures.append(f"{module_name}: parse error - {e}")

        if failures:
            pytest.fail("Missing exports:\n" + "\n".join(f"  - {f}" for f in failures))


class TestImportContract:
    """Test that top-level imports work as expected."""

    def test_top_level_imports_do_not_pull_deep(
        self, module_registry: list[str]
    ) -> None:
        """Verify that 'from vibe3.module import X' works for all modules.

        This validates the __init__.py re-export contract by importing
        one symbol from __all__ (if defined).
        """
        failures = []

        for module_name in module_registry:
            init_path = Path(f"src/vibe3/{module_name}/__init__.py")
            if not init_path.exists():
                continue

            try:
                # Import the module
                full_module_name = f"vibe3.{module_name}"
                module = importlib.import_module(full_module_name)

                # If module has __all__, test importing a symbol
                if hasattr(module, "__all__") and module.__all__:
                    # Pick the first symbol from __all__
                    symbol_name = module.__all__[0]
                    # Test: verify the symbol can be accessed via module
                    # This validates that re-export works
                    symbol = getattr(module, symbol_name)
                    # Verify it's not None (would indicate missing re-export)
                    if symbol is None:
                        failures.append(f"{module_name}: symbol {symbol_name} is None")

            except ImportError as e:
                failures.append(f"{module_name}: import failed - {e}")
            except (AttributeError, IndexError) as e:
                failures.append(f"{module_name}: __all__ error - {e}")
            except Exception as e:
                failures.append(f"{module_name}: unexpected error - {e}")

        if failures:
            pytest.fail(
                "Top-level imports failed:\n" + "\n".join(f"  - {f}" for f in failures)
            )
