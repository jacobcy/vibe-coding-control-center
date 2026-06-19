"""Tests for services/ sub-package architectural boundaries.

The services/ package contains 6 sub-packages with distinct responsibilities:
- shared/   : Cross-cutting utilities — must NOT import business sub-packages
- protocols/: Protocol definitions — must NOT import implementations
- flow/     : Core flow management
- pr/       : PR operations
- issue/    : Issue handling
- task/     : Task management
- orchestra/: Orchestration helpers

This test suite enforces internal boundaries that the generic top-level
modularity tests (test_module_api_compliance, test_dependency_direction)
cannot see.

Reference: GitHub issue #2578
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass

# Sub-packages that shared/ must NOT import from.
BUSINESS_SUBPACKAGES = [
    "vibe3.services.flow",
    "vibe3.services.pr",
    "vibe3.services.issue",
    "vibe3.services.task",
    "vibe3.services.orchestra",
]

# Sub-packages that protocols/ must NOT import from (implementations).
IMPLEMENTATION_SUBPACKAGES = [
    "vibe3.services.flow",
    "vibe3.services.pr",
    "vibe3.services.issue",
    "vibe3.services.task",
    "vibe3.services.orchestra",
    "vibe3.services.shared",
]

# Business sub-packages for coupling analysis.
SERVICES_SUBPACKAGES = ["flow", "pr", "issue", "task"]

# Known violations in shared/ boundary.
# Each entry: (relative_path, import_target) — registered as technical debt.
# These represent architectural debt that should be resolved over time.
# Phase 7b: All shared/ boundary violations resolved (2026-06-11).
KNOWN_SHARED_VIOLATIONS: set[tuple[str, str]] = set()

# Known bidirectional coupling between sub-packages.
# Format: (sub_a, sub_b) — both directions exist at sub-package level.
# All known cycles have been resolved as part of #2575 and #2902.
KNOWN_SUBPACKAGE_CYCLES: set[frozenset[str]] = set()


def _extract_imports_from_dir(
    directory: Path, prefix_filter: str = "vibe3.services"
) -> list[tuple[str, str]]:
    """Extract vibe3 imports from all .py files in a directory.

    Args:
        directory: Directory to scan
        prefix_filter: Only include imports starting with this prefix

    Returns:
        List of (source_file_relative, import_target) tuples
    """
    imports: list[tuple[str, str]] = []

    for py_file in directory.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith(prefix_filter):
                    imports.append(
                        (
                            str(py_file.relative_to(Path("src"))),
                            node.module,
                        )
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(prefix_filter):
                        imports.append(
                            (
                                str(py_file.relative_to(Path("src"))),
                                alias.name,
                            )
                        )

    return imports


def _extract_subpackage_imports(
    directory: Path,
) -> list[tuple[str, str]]:
    """Extract cross-subpackage imports (imports to OTHER services/ sub-packages).

    Args:
        directory: The source sub-package directory to scan

    Returns:
        List of (source_file, target_subpackage) tuples where target is a
        different sub-package than the source
    """
    results: list[tuple[str, str]] = []

    for py_file in directory.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, OSError):
            continue

        source_rel = str(py_file.relative_to(Path("src")))

        for node in ast.walk(tree):
            target: str | None = None

            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("vibe3.services."):
                    target = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("vibe3.services."):
                        target = alias.name

            if target is None:
                continue

            # Extract sub-package name (e.g. vibe3.services.flow.xxx -> flow)
            parts = target.split(".")
            if len(parts) >= 3:
                target_subpkg = parts[2]
                # Skip same sub-package and non-subpackage imports
                source_subpkg = directory.name
                if target_subpkg != source_subpkg:
                    results.append((source_rel, target_subpkg))

    return results


def _build_subpackage_dependency_graph() -> dict[str, set[str]]:
    """Build directed dependency graph between services/ sub-packages.

    Returns:
        Dict mapping sub-package name to set of sub-packages it imports from
    """
    graph: dict[str, set[str]] = {sp: set() for sp in SERVICES_SUBPACKAGES}
    services_dir = Path("src/vibe3/services")

    for subpkg in SERVICES_SUBPACKAGES:
        subpkg_dir = services_dir / subpkg
        if not subpkg_dir.exists():
            continue

        for _, target_subpkg in _extract_subpackage_imports(subpkg_dir):
            if target_subpkg in SERVICES_SUBPACKAGES:
                graph[subpkg].add(target_subpkg)

    return graph


class TestSharedBoundary:
    """Test that shared/ does not import business sub-packages."""

    def test_shared_no_business_imports(self) -> None:
        """shared/ must not import from flow/pr/issue/task/orchestra.

        shared/ provides cross-cutting utilities that all business
        sub-packages depend on. If shared/ imports from business sub-packages,
        it creates circular dependency risk and violates the utility layer
        contract.
        """
        shared_dir = Path("src/vibe3/services/shared")
        if not shared_dir.exists():
            pytest.skip("services/shared/ not found")

        imports = _extract_imports_from_dir(shared_dir)
        violations: list[str] = []

        for source_file, import_target in imports:
            for forbidden in BUSINESS_SUBPACKAGES:
                if import_target == forbidden or import_target.startswith(
                    forbidden + "."
                ):
                    if (source_file, import_target) in KNOWN_SHARED_VIOLATIONS:
                        continue
                    violations.append(f"{source_file}: imports {import_target}")

        if violations:
            pytest.fail(
                "shared/ must not import business sub-packages:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )


class TestProtocolsBoundary:
    """Test that protocols/ contains only protocol definitions."""

    def test_protocols_no_implementation_imports(self) -> None:
        """protocols/ must not import from implementation sub-packages.

        Protocol definitions should be pure interfaces — importing
        implementations defeats the purpose of dependency inversion.
        """
        protocols_dir = Path("src/vibe3/services/protocols")
        if not protocols_dir.exists():
            pytest.skip("services/protocols/ not found")

        imports = _extract_imports_from_dir(protocols_dir)
        violations: list[str] = []

        for source_file, import_target in imports:
            for forbidden in IMPLEMENTATION_SUBPACKAGES:
                if import_target == forbidden or import_target.startswith(
                    forbidden + "."
                ):
                    violations.append(f"{source_file}: imports {import_target}")

        if violations:
            pytest.fail(
                "protocols/ must not import implementation sub-packages:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )


class TestSubpackageCoupling:
    """Test inter-sub-package dependency structure."""

    def test_no_subpackage_bidirectional_coupling(self) -> None:
        """Sub-packages must not have bidirectional imports (cycles).

        Known exceptions are registered in KNOWN_SUBPACKAGE_CYCLES
        and tracked as technical debt.
        """
        graph = _build_subpackage_dependency_graph()

        bidirectional: list[str] = []

        for sub_a in SERVICES_SUBPACKAGES:
            for sub_b in SERVICES_SUBPACKAGES:
                if sub_a >= sub_b:
                    continue
                if sub_b in graph.get(sub_a, set()) and sub_a in graph.get(
                    sub_b, set()
                ):
                    pair = frozenset({sub_a, sub_b})
                    if pair not in KNOWN_SUBPACKAGE_CYCLES:
                        bidirectional.append(
                            f"{sub_a} <-> {sub_b} "
                            f"({sub_a} imports {sub_b}, {sub_b} imports {sub_a})"
                        )

        if bidirectional:
            pytest.fail(
                "Bidirectional coupling between sub-packages:\n"
                + "\n".join(f"  - {v}" for v in bidirectional)
            )

    def test_known_shared_violations_still_exist(self) -> None:
        """Verify known shared/ violations are still present.

        This test tracks technical debt: when a known violation is
        eliminated, it should be removed from KNOWN_SHARED_VIOLATIONS.
        If a violation disappears, this test will fail to remind us.
        """
        shared_dir = Path("src/vibe3/services/shared")
        if not shared_dir.exists():
            pytest.skip("services/shared/ not found")

        imports = _extract_imports_from_dir(shared_dir)
        actual_violations: set[tuple[str, str]] = set()

        for source_file, import_target in imports:
            for forbidden in BUSINESS_SUBPACKAGES:
                if import_target == forbidden or import_target.startswith(
                    forbidden + "."
                ):
                    actual_violations.add((source_file, import_target))

        stale = KNOWN_SHARED_VIOLATIONS - actual_violations
        if stale:
            pytest.fail(
                "Known shared/ violations no longer exist. "
                "Remove from KNOWN_SHARED_VIOLATIONS:\n"
                + "\n".join(f"  - {s}: {t}" for s, t in sorted(stale))
            )

    def test_known_subpackage_cycles_still_exist(self) -> None:
        """Verify no sub-package cycles exist.

        All known cycles have been resolved as part of #2575 and #2902.
        This test validates that no new cycles have been introduced.
        If cycles are found, add them to KNOWN_SUBPACKAGE_CYCLES for tracking
        and investigate resolution strategies.
        """
        graph = _build_subpackage_dependency_graph()

        actual_cycles: set[frozenset[str]] = set()
        unexpected: list[str] = []
        for sub_a in SERVICES_SUBPACKAGES:
            for sub_b in SERVICES_SUBPACKAGES:
                if sub_a >= sub_b:
                    continue
                if sub_b in graph.get(sub_a, set()) and sub_a in graph.get(
                    sub_b, set()
                ):
                    pair = frozenset({sub_a, sub_b})
                    actual_cycles.add(pair)
                    if pair not in KNOWN_SUBPACKAGE_CYCLES:
                        unexpected.append(
                            f"{sub_a} <-> {sub_b} "
                            f"({sub_a} imports {sub_b}, {sub_b} imports {sub_a})"
                        )

        if unexpected:
            pytest.fail(
                "Unexpected subpackage cycles detected — "
                "add to KNOWN_SUBPACKAGE_CYCLES or fix:\n"
                + "\n".join(f"  - {s}" for s in unexpected)
            )

        stale = KNOWN_SUBPACKAGE_CYCLES - actual_cycles
        if stale:
            pytest.fail(
                "Known subpackage cycles no longer exist. "
                "Remove from KNOWN_SUBPACKAGE_CYCLES:\n"
                + "\n".join(f"  - {sorted(s)}" for s in stale)
            )

        # All cycles resolved — this should pass without xfail

    def test_subpackage_dependency_report(self) -> None:
        """Print the full sub-package dependency graph for visibility.

        This test always passes — it's a diagnostic aid for humans
        reviewing the architecture.
        """
        graph = _build_subpackage_dependency_graph()

        lines = ["services/ sub-package dependency graph:"]
        for subpkg in SERVICES_SUBPACKAGES:
            deps = sorted(graph.get(subpkg, set()))
            if deps:
                lines.append(f"  {subpkg} -> {', '.join(deps)}")
            else:
                lines.append(f"  {subpkg} -> (none)")

        # Always passes — informational only
        assert True, "\n".join(lines)
