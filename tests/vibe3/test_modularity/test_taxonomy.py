"""Tests for runtime-kernel taxonomy compliance.

Validates that:
1. All L3 modules have a category assignment
2. Dependency directions follow category rules
3. Kernel (runtime + orchestra) does not import adapter/policy/observation internals
   at module level

Taxonomy alignment with kernel startup boundary (#2161/#2293):
  KERNEL: runtime, orchestra
  COMMAND_ADAPTER: execution, services
  POLICY: roles
  OBSERVATION: domain
  FORBIDDEN at startup: roles, agents, services, prompts, execution,
                        domain.handlers, domain.orchestration_facade
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from vibe3.runtime.taxonomy import (
    CATEGORY_ALLOWED_DEPS,
    MODULE_CATEGORY_MAP,
    ModuleCategory,
)

if TYPE_CHECKING:
    pass


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST | None]:
    """Build a mapping from each node to its parent node.

    Args:
        tree: The AST tree to analyze

    Returns:
        Dictionary mapping each node to its parent (or None for root)
    """
    parents = {}

    def _visit(node: ast.AST, parent: ast.AST | None = None) -> None:
        parents[node] = parent
        for child in ast.iter_child_nodes(node):
            _visit(child, node)

    _visit(tree)
    return parents


def _is_in_type_checking_or_function(
    node: ast.AST, parents: dict[ast.AST, ast.AST | None]
) -> bool:
    """Check if a node is inside a TYPE_CHECKING if block or a function/method body.

    Args:
        node: The AST node to check
        parents: Parent mapping from _build_parent_map

    Returns:
        True if node is inside TYPE_CHECKING block or function body
    """
    current = node
    while current is not None:
        parent = parents.get(current)
        if parent is None:
            break

        # Check if inside an if statement
        if isinstance(parent, ast.If):
            # Check if this is an `if TYPE_CHECKING:` block
            test = parent.test
            # Handle both `if TYPE_CHECKING:` and `if typing.TYPE_CHECKING:`
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                return True
            if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
                return True

        # Check if inside a function/method body
        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return True

        current = parent

    return False


def _get_module_level_imports(file_path: str) -> list[str]:
    """Extract module-level vibe3 imports from a Python file.

    Module-level imports are those at the top level of the file,
    not inside TYPE_CHECKING blocks or functions.

    Args:
        file_path: Path to Python file

    Returns:
        List of imported module names (full dotted paths)
    """
    try:
        source = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, OSError):
        return []

    parents = _build_parent_map(tree)
    imports: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            # Skip if inside TYPE_CHECKING or function
            if _is_in_type_checking_or_function(node, parents):
                continue
            for alias in node.names:
                if alias.name.startswith("vibe3"):
                    imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            # Skip if inside TYPE_CHECKING or function
            if _is_in_type_checking_or_function(node, parents):
                continue
            if node.module and node.module.startswith("vibe3"):
                # Try to identify if importing a submodule or a class/function
                for alias in node.names:
                    full_module = f"{node.module}.{alias.name}"
                    # Heuristic: lowercase first letter suggests submodule
                    if alias.name[0].islower():
                        imports.append(full_module)
                    else:
                        # Likely a class/function, just record the module
                        imports.append(node.module)

    return imports


def _get_category_for_module(module_name: str) -> ModuleCategory | None:
    """Get the category for a top-level vibe3 module.

    Args:
        module_name: Top-level module name (e.g., 'runtime', 'domain')

    Returns:
        ModuleCategory or None if not in taxonomy
    """
    return MODULE_CATEGORY_MAP.get(module_name)


class TestTaxonomyCompleteness:
    """Test that taxonomy is complete and consistent."""

    def test_all_l3_modules_have_category(
        self, module_layer_map: dict[str, int]
    ) -> None:
        """Verify every L3 module has a category assignment.

        L3 modules are derived from MODULE_LAYER_MAP (layer == 3).
        """
        # Get L3 modules from the layer map
        l3_modules = {name for name, layer in module_layer_map.items() if layer == 3}

        # Check each L3 module has a category
        missing_categories = []
        for module in l3_modules:
            if module not in MODULE_CATEGORY_MAP:
                missing_categories.append(module)

        if missing_categories:
            pytest.fail(
                "L3 modules missing category assignment: "
                f"{sorted(missing_categories)}\n"
                "Add them to MODULE_CATEGORY_MAP in src/vibe3/runtime/taxonomy.py"
            )

    def test_taxonomy_is_complete(self, module_layer_map: dict[str, int]) -> None:
        """Verify any new L3 module added to layer map must also appear in taxonomy.

        This test ensures the taxonomy stays in sync with the layer map.
        """
        # Get L3 modules from both sources
        l3_layer_modules = {
            name for name, layer in module_layer_map.items() if layer == 3
        }
        l3_taxonomy_modules = set(MODULE_CATEGORY_MAP.keys())

        # Find modules in layer map but not in taxonomy
        missing_from_taxonomy = l3_layer_modules - l3_taxonomy_modules

        # Find modules in taxonomy but not in layer map
        missing_from_layer_map = l3_taxonomy_modules - l3_layer_modules

        errors = []
        if missing_from_taxonomy:
            errors.append(
                f"Modules in L3 layer map but missing from taxonomy: "
                f"{sorted(missing_from_taxonomy)}"
            )
        if missing_from_layer_map:
            errors.append(
                f"Modules in taxonomy but not in L3 layer map: "
                f"{sorted(missing_from_layer_map)}"
            )

        if errors:
            pytest.fail("\n".join(errors))


class TestCategoryBoundaries:
    """Test that modules respect category boundaries."""

    def test_kernel_boundary(self) -> None:
        """Verify kernel (runtime) only imports KERNEL-category modules at module level.

        Kernel: only itself, orchestra (also KERNEL), and L4-L6 are allowed.
        Lazy/__getattr__ imports inside functions are acceptable per existing
        pattern — this test checks module-level only.
        """
        runtime_init = "src/vibe3/runtime/__init__.py"
        imports = _get_module_level_imports(runtime_init)

        # Extract top-level modules from imports
        imported_modules = set()
        for imp in imports:
            if not imp.startswith("vibe3."):
                continue
            parts = imp.split(".")
            if len(parts) >= 2:
                imported_modules.add(parts[1])  # e.g., 'services'

        # Check for violations
        violations = []
        for module in imported_modules:
            if module == "runtime":
                continue  # Self-import is allowed

            category = _get_category_for_module(module)
            if category is None:
                continue  # Module not in taxonomy (e.g., L6 modules)

            # Kernel should not import from other categories
            if category != ModuleCategory.KERNEL:
                violations.append(
                    f"runtime (KERNEL) imports from {module} ({category.name})"
                )

        if violations:
            pytest.fail(
                "Kernel boundary violations found:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )


class TestCategoryDependencyDirection:
    """Test that dependencies follow category rules."""

    def test_category_dependency_direction(
        self, import_graph: dict[str, list[str]], module_layer_map: dict[str, int]
    ) -> None:
        """Verify imports respect category dependency rules.

        Category N may only import from categories <= N.
        """
        violations = []

        # Get L3 modules
        l3_modules = {name for name, layer in module_layer_map.items() if layer == 3}

        for source_module, imports in import_graph.items():
            # Only check L3 modules
            if source_module not in l3_modules:
                continue

            # Get source category
            source_category = _get_category_for_module(source_module)
            if source_category is None:
                continue

            # Get allowed categories for this source
            allowed_categories = CATEGORY_ALLOWED_DEPS.get(source_category, set())

            for target_module in imports:
                # Only check L3 targets
                if target_module not in l3_modules:
                    continue

                # Get target category
                target_category = _get_category_for_module(target_module)
                if target_category is None:
                    continue

                # Check if target category is allowed
                if target_category not in allowed_categories:
                    violations.append(
                        f"{source_module} ({source_category.name}) → "
                        f"{target_module} ({target_category.name}): "
                        f"allowed categories are {[c.name for c in allowed_categories]}"
                    )

        if violations:
            pytest.fail(
                "Category dependency violations found:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
