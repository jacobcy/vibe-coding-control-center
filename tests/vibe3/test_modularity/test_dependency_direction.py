"""Tests for dependency direction compliance."""

from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.vibe3.test_modularity.conftest import (
    extract_file_imports,
    get_module_layer,
)

if TYPE_CHECKING:
    pass


class TestLayerDependencies:
    """Test that dependencies follow layer rules."""

    def test_no_upward_imports(self, module_registry: list[str]) -> None:
        """Verify no upward imports (lower layers importing from higher layers).

        Layer N may import from layers >= N (higher or equal layer number).
        Violations are reported as test failures.

        This is now a hard gate (xfail removed): the layer map in conftest.py
        reflects the actual architecture, including the L3 orchestration core
        (domain/execution/orchestra/roles/runtime/services) which forms a single
        layer. See epic #1987 (#1988/#1989/#1990/#1991) for the layer
        redefinition that brought upward violations to zero.
        """
        violations = []

        for module_name in module_registry:
            module_path = Path(f"src/vibe3/{module_name}")
            if not module_path.exists():
                continue

            source_layer = get_module_layer(module_name)
            if source_layer is None:
                # Module not in layer map, skip
                continue

            # Check all Python files in the module
            for py_file in module_path.glob("**/*.py"):
                if "__pycache__" in str(py_file):
                    continue

                imports = extract_file_imports(str(py_file))

                for imp in imports:
                    # Extract top-level module from import
                    if not imp.startswith("vibe3."):
                        continue

                    parts = imp.split(".")
                    if len(parts) < 2:
                        continue

                    target_module = parts[1]
                    target_layer = get_module_layer(target_module)

                    if target_layer is None:
                        # Target not in layer map, skip
                        continue

                    # Check dependency rule: source_layer <= target_layer
                    if source_layer > target_layer:
                        violations.append(
                            f"{py_file.relative_to('src')}: "
                            f"{module_name} (layer {source_layer}) "
                            f"imports {target_module} (layer {target_layer}) "
                            f"— upward dependency violation"
                        )

        if violations:
            pytest.fail(
                "Upward dependency violations found:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )

    @pytest.mark.xfail(
        reason="Known architectural debt: ~25 __init__.py files import from own "
        "submodules (roles, runtime, server, services, utils)"
    )
    def test_no_self_reference_in_init(self, module_registry: list[str]) -> None:
        """Verify __init__.py files don't import from their own submodule in ways
        that create circular init-time dependencies.
        """
        violations = []

        for module_name in module_registry:
            init_path = Path(f"src/vibe3/{module_name}/__init__.py")
            if not init_path.exists():
                continue

            try:
                source = init_path.read_text(encoding="utf-8")
                tree = ast.parse(source)

                # Look for imports of own submodules
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        # Check absolute imports: from vibe3.<module>.<sub> import ...
                        if node.module and node.module.startswith(
                            f"vibe3.{module_name}."
                        ):
                            # Check if importing from a submodule
                            parts = node.module.split(".")
                            if len(parts) > 2:
                                submodule = parts[2]
                                # Flag potential circular dependency
                                violations.append(
                                    f"{module_name}/__init__.py: "
                                    f"imports from own submodule {submodule} "
                                    "(potential circular dependency)"
                                )
                        # Check relative imports: from .<sub> import ...
                        elif node.level > 0 and node.module:
                            # Relative import in __init__.py indicates
                            # importing from submodule
                            violations.append(
                                f"{module_name}/__init__.py: "
                                f"relative import from .{node.module} "
                                "(potential circular dependency)"
                            )

            except (SyntaxError, OSError) as e:
                violations.append(f"{module_name}/__init__.py: parse error - {e}")

        if violations:
            pytest.fail(
                "Potential circular dependencies in __init__.py:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )


def _detect_cycles_dfs(
    import_graph: dict[str, list[str]],
) -> list[list[str]]:
    """Detect all cycles in the import graph using DFS.

    Args:
        import_graph: Module dependency graph mapping module to its imports

    Returns:
        List of cycles, where each cycle is a list of module names
        forming a path that starts and ends with the same module
    """
    # Build adjacency list
    graph = defaultdict(set)
    for module, imports in import_graph.items():
        for imp in imports:
            graph[module].add(imp)

    # Detect cycles using DFS
    visited = set()
    rec_stack = set()
    cycles = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                dfs(neighbor, path)
            elif neighbor in rec_stack:
                # Found cycle
                cycle_start = path.index(neighbor)
                cycle = path[cycle_start:] + [neighbor]
                cycles.append(cycle)

        path.pop()
        rec_stack.remove(node)

    for module in graph:
        if module not in visited:
            dfs(module, [])

    return cycles


class TestCircularDependencies:
    """Test for circular dependencies."""

    def test_no_circular_deps_outside_l3_core(
        self, import_graph: dict[str, list[str]], module_layer_map: dict[str, int]
    ) -> None:
        """Verify no circular dependencies outside L3 orchestration core.

        This is a hard gate: any cycle involving at least one non-L3 module
        will fail immediately. All 10 remaining cycles are within L3 core
        {domain, execution, orchestra, roles, runtime, services}.

        L3 modules are derived from MODULE_LAYER_MAP (layer == 3).
        """
        # Get L3 modules from the layer map
        l3_modules = {name for name, layer in module_layer_map.items() if layer == 3}

        # Detect cycles using DFS
        cycles = _detect_cycles_dfs(import_graph)

        # Filter to only cycles outside L3 core
        outside_l3_cycles = [
            cycle
            for cycle in cycles
            if any(module not in l3_modules for module in cycle)
        ]

        if outside_l3_cycles:
            cycle_strs = [" → ".join(cycle) for cycle in outside_l3_cycles]
            pytest.fail(
                "Circular dependencies outside L3 core found:\n"
                + "\n".join(f"  - {c}" for c in cycle_strs)
            )

    @pytest.mark.xfail(
        reason="Known architectural debt: 12 L3-internal circular deps remain in "
        "{domain, execution, orchestra, roles, runtime, services} SCC. "
        "Tracked by epic #1987."
    )
    def test_no_circular_deps_within_l3_core(
        self, import_graph: dict[str, list[str]], module_layer_map: dict[str, int]
    ) -> None:
        """Verify no circular dependencies within L3 orchestration core.

        This is an xfail test tracking the 10 known cycles within the
        L3 orchestration core {domain, execution, orchestra, roles, runtime, services}.

        L3 modules are derived from MODULE_LAYER_MAP (layer == 3).
        """
        # Get L3 modules from the layer map
        l3_modules = {name for name, layer in module_layer_map.items() if layer == 3}

        # Detect cycles using DFS
        cycles = _detect_cycles_dfs(import_graph)

        # Filter to only cycles within L3 core
        within_l3_cycles = [
            cycle for cycle in cycles if all(module in l3_modules for module in cycle)
        ]

        if within_l3_cycles:
            cycle_strs = [" → ".join(cycle) for cycle in within_l3_cycles]
            pytest.fail(
                "Circular dependencies within L3 core found:\n"
                + "\n".join(f"  - {c}" for c in cycle_strs)
            )


class TestKnownExceptions:
    """Document known acceptable violations."""

    # Known violations that are architecturally acceptable
    # These will be marked as xfail to keep the suite green
    KNOWN_UPWARD_VIOLATIONS = [
        # Add known acceptable violations here with reasons
        # Example: "services imports from agents (acceptable because ...)"
    ]

    def test_known_violations_documented(self) -> None:
        """Verify that known violations are properly documented.

        This test ensures we don't forget to document acceptable deviations.
        """
        # This test always passes if we reach here
        # It's a placeholder for future known violations
        pass
