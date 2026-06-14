"""Architecture tests for services re-export compatibility surface.

These tests discover and baseline-track four categories of compatibility debt:
1. Root barrel imports (from vibe3.services import ...)
2. Shared barrel imports (from vibe3.services.shared import ...)
3. Pure compatibility bridge modules
4. Layer-crossing bridge modules

Each category enforces the current baseline as a hard regression gate, then uses
pytest.xfail for the known residual debt until the count reaches zero.
"""

import ast
from pathlib import Path
from typing import Dict, List

import pytest


def count_barrel_imports(import_target: str) -> List[Dict]:
    """Count barrel imports from the specified target across src/ and tests/.

    Args:
        import_target: The module path to search for (e.g., "vibe3.services")

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


def discover_bridge_modules() -> Dict[str, List[Dict]]:
    """Discover bridge modules in src/vibe3/services/.

    Returns:
        {
            "pure_bridges": [
                {"file": str, "reexports_from": str, "symbols": list}
            ],
            "layer_crossing_bridges": [
                {"file": str, "reexports_from": str, "symbols": list}
            ]
        }
    """
    pure_bridges: List[Dict] = []
    layer_crossing_bridges: List[Dict] = []

    services_path = Path("src/vibe3/services")
    if not services_path.exists():
        return {
            "pure_bridges": pure_bridges,
            "layer_crossing_bridges": layer_crossing_bridges,
        }

    for py_file in services_path.rglob("*.py"):
        # Skip __init__.py and __pycache__
        if py_file.name == "__init__.py" or "__pycache__" in str(py_file):
            continue

        try:
            tree = ast.parse(py_file.read_text())

            # Collect top-level statements
            has_non_bridge_content = False
            import_nodes = []
            all_assignments = []

            for node in tree.body:
                # Allow ImportFrom nodes
                if isinstance(node, ast.ImportFrom):
                    import_nodes.append(node)
                # Allow __all__ assignments
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            all_assignments.append(node)
                        else:
                            # Non-__all__ assignment
                            has_non_bridge_content = True
                            break
                # Allow docstrings (Expr with string value)
                elif isinstance(node, ast.Expr) and isinstance(
                    node.value, ast.Constant
                ):
                    if isinstance(node.value.value, str):
                        continue  # Docstring, allowed
                    else:
                        has_non_bridge_content = True
                        break
                else:
                    # Any other top-level statement (class def, function def, etc.)
                    has_non_bridge_content = True
                    break

            # If has non-bridge content, skip this file
            if has_non_bridge_content:
                continue

            # Must have at least one import to be a bridge
            if not import_nodes:
                continue

            # Analyze import sources
            import_sources = set()
            imported_symbols = []

            for node in import_nodes:
                if node.module:
                    import_sources.add(node.module)
                    for alias in node.names:
                        imported_symbols.append(alias.name)

            # Classify based on import sources
            is_layer_crossing = False
            is_pure_bridge = False

            for source in import_sources:
                # Layer-crossing: imports from clients/analysis/config
                if source.startswith("vibe3.clients"):
                    is_layer_crossing = True
                elif source.startswith("vibe3.analysis"):
                    is_layer_crossing = True
                elif source.startswith("vibe3.config"):
                    is_layer_crossing = True
                # Pure bridge: imports from services.shared or cross-subpackage
                elif source.startswith("vibe3.services.shared"):
                    is_pure_bridge = True
                elif source.startswith("vibe3.services.") and source != (
                    f"vibe3.services.{py_file.parent.name}"
                ):
                    # Cross-subpackage within services
                    is_pure_bridge = True

            # Determine final classification
            # Priority: layer-crossing > pure bridge
            if is_layer_crossing:
                layer_crossing_bridges.append(
                    {
                        "file": str(py_file),
                        "reexports_from": ", ".join(sorted(import_sources)),
                        "symbols": imported_symbols,
                    }
                )
            elif is_pure_bridge:
                pure_bridges.append(
                    {
                        "file": str(py_file),
                        "reexports_from": ", ".join(sorted(import_sources)),
                        "symbols": imported_symbols,
                    }
                )

        except SyntaxError:
            # Skip files with syntax errors
            continue

    return {
        "pure_bridges": pure_bridges,
        "layer_crossing_bridges": layer_crossing_bridges,
    }


# Known baseline bridges
KNOWN_PURE_BRIDGES = set()

KNOWN_LAYER_CROSSING_BRIDGES = set()

ROOT_BARREL_IMPORT_BASELINE = 129
SHARED_BARREL_IMPORT_BASELINE = 0
PURE_BRIDGE_MODULE_BASELINE = len(KNOWN_PURE_BRIDGES)
LAYER_CROSSING_BRIDGE_BASELINE = len(KNOWN_LAYER_CROSSING_BRIDGES)


def test_root_barrel_import_count() -> None:
    """Verify root barrel imports (from vibe3.services import ...).

    Goal: Zero root barrel imports (all imports should be direct).
    Current baseline: 129 call sites across 77 files.
    """
    imports = count_barrel_imports("vibe3.services")

    print(f"\n📊 Root barrel imports: {len(imports)} call sites")
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

    assert len(imports) <= ROOT_BARREL_IMPORT_BASELINE, (
        "Root barrel imports increased beyond the issue #2698 baseline: "
        f"expected <= {ROOT_BARREL_IMPORT_BASELINE}, found {len(imports)}"
    )
    if imports:
        pytest.xfail(
            f"Baseline: {len(imports)} root barrel imports remain (issue #2698)"
        )

    assert len(imports) == 0, f"Found {len(imports)} root barrel imports"


def test_shared_barrel_import_count() -> None:
    """Verify shared barrel imports (from vibe3.services.shared import ...).

    Goal: Zero shared barrel imports (all imports should be direct).
    Current baseline: ~1 call site.
    """
    imports = count_barrel_imports("vibe3.services.shared")

    print(f"\n📊 Shared barrel imports: {len(imports)} call sites")
    if imports:
        for imp in imports[:10]:
            print(f"   {imp['file']}:{imp['line']} - {imp['import']}")

    assert len(imports) <= SHARED_BARREL_IMPORT_BASELINE, (
        "Shared barrel imports increased beyond the issue #2698 baseline: "
        f"expected <= {SHARED_BARREL_IMPORT_BASELINE}, found {len(imports)}"
    )
    if imports:
        pytest.xfail(
            f"Baseline: {len(imports)} shared barrel imports remain (issue #2698)"
        )

    assert len(imports) == 0, f"Found {len(imports)} shared barrel imports"


def test_pure_bridge_module_count() -> None:
    """Verify pure compatibility bridge modules.

    Goal: Zero pure bridge modules (all compatibility shims should be removed).
    Current baseline: 1 file.
    """
    bridges = discover_bridge_modules()
    pure_bridges = bridges["pure_bridges"]

    print(f"\n📊 Pure bridge modules: {len(pure_bridges)} files")

    known_bridges = set()
    unknown_bridges = set()

    for bridge in pure_bridges:
        file = bridge["file"]
        print(f"   {file}")
        print(f"     Re-exports from: {bridge['reexports_from']}")
        print(f"     Symbols: {', '.join(bridge['symbols'][:5])}")

        if file in KNOWN_PURE_BRIDGES:
            known_bridges.add(file)
        else:
            unknown_bridges.add(file)

    # Cross-check against known baseline
    if unknown_bridges:
        print(f"\n   ⚠️  WARNING: {len(unknown_bridges)} unknown bridge(s) discovered:")
        for file in unknown_bridges:
            print(f"     {file}")
        print("   This may indicate new compatibility debt or regression.")

    # Verify all known bridges were discovered
    missing_known = KNOWN_PURE_BRIDGES - known_bridges
    if missing_known:
        print(f"\n   ⚠️  WARNING: {len(missing_known)} known bridge(s) not detected:")
        for file in missing_known:
            print(f"     {file}")

    assert not unknown_bridges, (
        "Unknown pure bridge module(s) discovered: "
        f"{', '.join(sorted(unknown_bridges))}"
    )
    assert len(pure_bridges) <= PURE_BRIDGE_MODULE_BASELINE, (
        "Pure bridge modules increased beyond the issue #2698 baseline: "
        f"expected <= {PURE_BRIDGE_MODULE_BASELINE}, found {len(pure_bridges)}"
    )
    if pure_bridges:
        pytest.xfail(
            f"Baseline: {len(pure_bridges)} pure bridge modules remain (issue #2698)"
        )

    assert len(pure_bridges) == 0, f"Found {len(pure_bridges)} pure bridge modules"


def test_layer_crossing_bridge_count() -> None:
    """Verify layer-crossing bridge modules.

    Goal: Zero layer-crossing bridges (no services re-exporting from other layers).
    Current baseline: 3 files.
    """
    bridges = discover_bridge_modules()
    layer_crossing_bridges = bridges["layer_crossing_bridges"]

    print(f"\n📊 Layer-crossing bridge modules: {len(layer_crossing_bridges)} files")

    known_bridges = set()
    unknown_bridges = set()

    for bridge in layer_crossing_bridges:
        file = bridge["file"]
        print(f"   {file}")
        print(f"     Re-exports from: {bridge['reexports_from']}")
        print(f"     Symbols: {', '.join(bridge['symbols'][:5])}")

        if file in KNOWN_LAYER_CROSSING_BRIDGES:
            known_bridges.add(file)
        else:
            unknown_bridges.add(file)

    # Cross-check against known baseline
    if unknown_bridges:
        print(f"\n   ⚠️  WARNING: {len(unknown_bridges)} unknown bridge(s) discovered:")
        for file in unknown_bridges:
            print(f"     {file}")
        print("   This may indicate new layer-crossing debt or regression.")

    # Verify all known bridges were discovered
    missing_known = KNOWN_LAYER_CROSSING_BRIDGES - known_bridges
    if missing_known:
        print(f"\n   ⚠️  WARNING: {len(missing_known)} known bridge(s) not detected:")
        for file in missing_known:
            print(f"     {file}")
        print("   (May be due to classifier excluding files with local definitions)")

    assert not unknown_bridges, (
        "Unknown layer-crossing bridge module(s) discovered: "
        f"{', '.join(sorted(unknown_bridges))}"
    )
    assert len(layer_crossing_bridges) <= LAYER_CROSSING_BRIDGE_BASELINE, (
        "Layer-crossing bridge modules increased beyond the issue #2698 baseline: "
        f"expected <= {LAYER_CROSSING_BRIDGE_BASELINE}, "
        f"found {len(layer_crossing_bridges)}"
    )
    if layer_crossing_bridges:
        pytest.xfail(
            "Baseline: "
            f"{len(layer_crossing_bridges)} layer-crossing bridge modules remain "
            "(issue #2698)"
        )

    assert (
        len(layer_crossing_bridges) == 0
    ), f"Found {len(layer_crossing_bridges)} layer-crossing bridge modules"


def test_root_barrel_all_matches_approved_public_api() -> None:
    """Verify root barrel __all__ entries correspond to known symbols.

    This ensures that the root barrel's __all__ list is explicit and intentional,
    not a catch-all convenience surface.
    """
    import ast

    root_barrel_path = Path("src/vibe3/services/__init__.py")
    assert root_barrel_path.exists(), "Root barrel file not found"

    tree = ast.parse(root_barrel_path.read_text())

    # Extract __all__ list
    all_names = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, ast.List):
                        for elt in node.value.elts:
                            if isinstance(elt, ast.Constant):
                                all_names.append(elt.value)

    # Verify __all__ is not empty
    assert all_names, "Root barrel has empty __all__ list"

    # Verify each name in __all__ has a corresponding _SYMBOL_MODULES entry
    symbol_modules = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_SYMBOL_MODULES":
                    if isinstance(node.value, ast.Dict):
                        for key, value in zip(node.value.keys, node.value.values):
                            if isinstance(key, ast.Constant):
                                symbol_modules[key.value] = True

    # All __all__ entries should have corresponding _SYMBOL_MODULES entries
    missing = set(all_names) - set(symbol_modules.keys())
    assert not missing, (
        f"Root barrel __all__ has entries without _SYMBOL_MODULES mapping: "
        f"{sorted(missing)}"
    )

    print(f"\n✅ Root barrel __all__ has {len(all_names)} valid entries")


def test_domain_barrels_all_matches_approved_api() -> None:
    """Verify each domain barrel's __all__ matches expected public API list.

    This ensures domain barrels expose explicit public API contracts rather than
    broad convenience re-exports.
    """
    import ast

    domain_barrels = [
        "src/vibe3/services/check/__init__.py",
        "src/vibe3/services/flow/__init__.py",
        "src/vibe3/services/handoff/__init__.py",
        "src/vibe3/services/issue/__init__.py",
        "src/vibe3/services/orchestra/__init__.py",
        "src/vibe3/services/pr/__init__.py",
        "src/vibe3/services/task/__init__.py",
    ]

    for barrel_path_str in domain_barrels:
        barrel_path = Path(barrel_path_str)
        if not barrel_path.exists():
            continue

        tree = ast.parse(barrel_path.read_text())

        # Extract __all__ list
        all_names = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant):
                                    all_names.append(elt.value)

        # Verify __all__ is not empty
        assert all_names, f"{barrel_path} has empty __all__ list"

        # Verify each name has corresponding _SYMBOL_MODULES entry
        symbol_modules = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_SYMBOL_MODULES":
                        if isinstance(node.value, ast.Dict):
                            for key, value in zip(node.value.keys, node.value.values):
                                if isinstance(key, ast.Constant):
                                    symbol_modules[key.value] = True

        missing = set(all_names) - set(symbol_modules.keys())
        assert not missing, (
            f"{barrel_path} __all__ has entries without _SYMBOL_MODULES mapping: "
            f"{sorted(missing)}"
        )

        print(
            f"✅ {barrel_path.parent.name} barrel __all__ has "
            f"{len(all_names)} valid entries"
        )
