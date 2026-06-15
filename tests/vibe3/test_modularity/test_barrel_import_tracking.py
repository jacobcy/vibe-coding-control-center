"""Barrel import tracking for vibe3.exceptions and vibe3.config.

These tests establish baselines for barrel imports to detect regression
and prevent growth. They use AST parsing (same approach as
test_services_reexport_surface.py) for fast, reliable import detection.
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

    Goal: Prevent growth of exceptions barrel imports.
    Baseline: 161 call sites (as of issue #2848).

    Most barrel imports are for exception TYPES (GitError, GitHubError, etc.)
    which are defined directly in exceptions/__init__.py and safe for mypy.
    A few are for lazy FUNCTIONS (classify_error_hybrid, get_error_handling_contract)
    which are problematic and should be migrated to direct submodule imports.
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

    Goal: Prevent growth of config barrel imports.
    Baseline: 140 call sites (as of issue #2848).

    The config barrel uses lazy __getattr__ for re-exports, which is safe
    when importing TYPES (ConventionResolver, OrchestraConfig) but can
    break mypy when importing FUNCTIONS or when the import graph is perturbed.
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
    baseline = 140

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
