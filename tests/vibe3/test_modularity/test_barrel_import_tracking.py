"""Barrel import tracking for vibe3.exceptions and vibe3.config.

These tests establish baselines for barrel imports as risk/trend observation.
They prevent uncontrolled growth of barrel import call sites but do NOT imply
that barrel imports should be replaced with deep imports. Barrel imports through
public API are the correct pattern per modularity-standards.md.

Uses AST parsing (same approach as test_services_reexport_surface.py)
for fast, reliable import detection.
"""

import ast
from pathlib import Path
from typing import Dict, List

import pytest


def count_barrel_imports(import_target: str) -> List[Dict]:
    """Count barrel imports from the specified target across src/ and tests/.

    Args:
        import_target: The module path to search for (e.g., "vibe3.exceptions")

    Returns:
        List of {"file": str, "line": int, "import": str} dicts
    """
    imports = []

    for root in [Path("src"), Path("tests")]:
        if not root.exists():
            continue

        for py_file in root.rglob("*.py"):
            # Skip __pycache__ and .pyc
            if "__pycache__" in str(py_file):
                continue

            try:
                tree = ast.parse(py_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        # Check if importing from the barrel target
                        if module == import_target:
                            imported_names = ", ".join(
                                alias.name for alias in node.names
                            )
                            imports.append(
                                {
                                    "file": str(py_file),
                                    "line": node.lineno,
                                    "import": f"from {module} import {imported_names}",
                                }
                            )
            except SyntaxError:
                # Skip files with syntax errors
                continue

    return imports


def test_exceptions_barrel_import_count() -> None:
    """Track barrel imports from vibe3.exceptions across src/ and tests/.

    Goal: Prevent uncontrolled growth of exceptions barrel imports.
    Baseline: 161 call sites (as of issue #2848).

    Most barrel imports are for exception TYPES (GitError, GitHubError, etc.)
    which are defined directly in exceptions/__init__.py — these are legitimate
    public API imports. A subset are lazy FUNCTIONS (classify_error_hybrid,
    get_error_handling_contract) accessed through the barrel's __getattr__;
    these are also valid public API usage but warrant awareness for dependency
    direction (e.g., an L6 module depending on error classification logic).

    This is a risk/trend observation baseline. It does NOT prescribe migrating
    barrel imports to deep imports — public API is the contract.
    """
    imports = count_barrel_imports("vibe3.exceptions")

    print(f"\n📊 vibe3.exceptions barrel imports: {len(imports)} call sites")
    if imports:
        # Group by file
        file_counts: Dict[str, int] = {}
        for imp in imports:
            file = imp["file"]
            file_counts[file] = file_counts.get(file, 0) + 1

        print(f"   Across {len(file_counts)} files")
        print("\n   Top 10 files:")
        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        for file, count in sorted_files[:10]:
            print(f"     {file}: {count} imports")

    # Baseline established at issue #2848
    baseline = 161

    # Hard gate: prevent growth beyond baseline
    assert len(imports) <= baseline, (
        f"vibe3.exceptions barrel imports increased: "
        f"expected <= {baseline}, found {len(imports)}"
    )

    # Expected state: baseline violations remain (tracked by issue #2848)
    if imports:
        pytest.xfail(
            f"Baseline: {len(imports)} vibe3.exceptions barrel imports remain "
            f"(issue #2848)"
        )


def test_config_barrel_import_count() -> None:
    """Track barrel imports from vibe3.config across src/ and tests/.

    Goal: Prevent uncontrolled growth of config barrel imports.
    Baseline: 140 call sites (as of issue #2848).

    The config barrel uses lazy __getattr__ with TYPE_CHECKING blocks for
    re-exports. When mypy has proper project context, TYPE_CHECKING provides
    full type information. This baseline tracks import volume as a trend
    indicator, not as a list of violations to migrate away from.
    """
    imports = count_barrel_imports("vibe3.config")

    print(f"\n📊 vibe3.config barrel imports: {len(imports)} call sites")
    if imports:
        # Group by file
        file_counts: Dict[str, int] = {}
        for imp in imports:
            file = imp["file"]
            file_counts[file] = file_counts.get(file, 0) + 1

        print(f"   Across {len(file_counts)} files")
        print("\n   Top 10 files:")
        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        for file, count in sorted_files[:10]:
            print(f"     {file}: {count} imports")

    # Baseline established at issue #2848
    # Updated for #2912 (+2), #2938 (+1), #2939 (+1), #2945 (+1), #2869 (+1)
    baseline = 146

    # Hard gate: prevent growth beyond baseline
    assert len(imports) <= baseline, (
        f"vibe3.config barrel imports increased: "
        f"expected <= {baseline}, found {len(imports)}"
    )

    # Expected state: baseline violations remain (tracked by issue #2848)
    if imports:
        pytest.xfail(
            f"Baseline: {len(imports)} vibe3.config barrel imports remain "
            f"(issue #2848)"
        )
