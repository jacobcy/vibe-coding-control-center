#!/usr/bin/env python3
"""
Step 1: AST scan to detect all external consumption of services symbols.

Scans all non-services .py files in src/vibe3/ and tests/vibe3/ to find
all `from vibe3.services.<submodule> import <symbol>` statements.
"""

import ast
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple


def scan_file_for_services_imports(file_path: Path) -> List[Tuple[str, str, int, bool]]:
    """
    Scan a single file for services imports.

    Returns list of (submodule, symbol, line_number, is_lazy) tuples.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Could not parse {file_path}: {e}")
        return []

    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # Check if this is a services import
            if node.module and node.module.startswith('vibe3.services.'):
                # Extract submodule (e.g., 'flow_service' from 'vibe3.services.flow_service')
                parts = node.module.split('.')
                if len(parts) >= 3:
                    submodule = parts[2]  # vibe3.services.<submodule>

                    # Check if this is inside a function (lazy import)
                    is_lazy = False
                    for parent in ast.walk(tree):
                        if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            for child in ast.walk(parent):
                                if child is node:
                                    is_lazy = True
                                    break

                    # Extract imported symbols
                    for alias in node.names:
                        symbol = alias.name
                        imports.append((submodule, symbol, node.lineno, is_lazy))

    return imports


def scan_directory(base_path: Path, exclude_dirs: Set[str]) -> Dict[str, Set[str]]:
    """
    Scan all .py files in directory (excluding certain dirs).

    Returns {submodule: {symbols}} mapping.
    """
    symbols_map = defaultdict(set)
    import_count = 0
    lazy_count = 0

    for py_file in base_path.rglob('*.py'):
        # Skip excluded directories
        if any(excluded in py_file.parts for excluded in exclude_dirs):
            continue

        # Skip __pycache__
        if '__pycache__' in py_file.parts:
            continue

        imports = scan_file_for_services_imports(py_file)
        for submodule, symbol, line_no, is_lazy in imports:
            symbols_map[submodule].add(symbol)
            import_count += 1
            if is_lazy:
                lazy_count += 1
                print(f"  Lazy import: {py_file.relative_to(base_path)}:{line_no} - {submodule}.{symbol}")

    return dict(symbols_map), import_count, lazy_count


def main():
    print("=" * 80)
    print("Step 1: Scanning for external services imports")
    print("=" * 80)

    # Scan src/vibe3/ (excluding services/)
    print("\nScanning src/vibe3/ (excluding services/)...")
    src_path = Path('src/vibe3')
    src_symbols, src_count, src_lazy = scan_directory(src_path, {'services'})

    # Scan tests/vibe3/ (excluding services/)
    print("\nScanning tests/vibe3/ (excluding services/)...")
    test_path = Path('tests/vibe3')
    test_symbols, test_count, test_lazy = scan_directory(test_path, {'services'})

    # Merge results
    all_symbols = defaultdict(set)
    for submodule, symbols in src_symbols.items():
        all_symbols[submodule].update(symbols)
    for submodule, symbols in test_symbols.items():
        all_symbols[submodule].update(symbols)

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total import statements: {src_count + test_count}")
    print(f"  - src/vibe3/: {src_count} ({src_lazy} lazy)")
    print(f"  - tests/vibe3/: {test_count} ({test_lazy} lazy)")
    print(f"\nTotal submodules: {len(all_symbols)}")
    print(f"Total unique symbols: {sum(len(s) for s in all_symbols.values())}")

    # Print detailed mapping
    print("\n" + "=" * 80)
    print("SUBMODULE -> SYMBOLS MAPPING")
    print("=" * 80)

    for submodule in sorted(all_symbols.keys()):
        symbols = sorted(all_symbols[submodule])
        print(f"\n{submodule} ({len(symbols)} symbols):")
        for i, symbol in enumerate(symbols):
            if i % 5 == 0:
                print("  ", end="")
            print(f"{symbol}", end="")
            if i % 5 == 4 or i == len(symbols) - 1:
                print()
            else:
                print(", ", end="")

    # Special checks as per plan
    print("\n" + "=" * 80)
    print("SPECIAL CHECKS")
    print("=" * 80)

    special_modules = ['flow_classifier', 'orchestra_status_service', 'scan_service', 'task_status_classifier']
    for module in special_modules:
        if module in all_symbols:
            print(f"\n{module}: {sorted(all_symbols[module])}")
        else:
            print(f"\n{module}: NOT FOUND (may only be used via multiline imports)")

    # Output Python code for Step 2
    print("\n" + "=" * 80)
    print("PYTHON CODE FOR STEP 2")
    print("=" * 80)
    print("\n# Copy this into services/__init__.py:\n")
    for submodule in sorted(all_symbols.keys()):
        symbols = sorted(all_symbols[submodule])
        print(f"from vibe3.services.{submodule} import {', '.join(symbols)}")

    print(f"\n# Total: {len(all_symbols)} submodules, {sum(len(s) for s in all_symbols.values())} symbols")


if __name__ == '__main__':
    main()
