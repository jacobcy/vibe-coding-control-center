#!/usr/bin/env python3
"""
Step 3: Simple regex-based refactoring of services imports.

This approach is more reliable than AST-based transformation for this specific use case.
"""

import re
from pathlib import Path
from typing import List, Tuple


def refactor_file(file_path: Path) -> Tuple[bool, str]:
    """
    Refactor services imports in a single file using regex.

    Returns (was_modified, error_message).
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Pattern to match: from vibe3.services.<submodule> import <symbols>
        # This handles both single-line and multi-line imports
        pattern = r'from\s+vibe3\.services\.\w+\s+import\s+'

        # Replace with: from vibe3.services import <symbols>
        content = re.sub(pattern, 'from vibe3.services import ', content)

        if content == original_content:
            return False, ""

        # Verify syntax
        import ast
        try:
            ast.parse(content)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        # Write back
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return True, ""

    except Exception as e:
        return False, str(e)


def main():
    print("=" * 80)
    print("Step 3: Refactoring services imports")
    print("=" * 80)

    # Collect files to process
    files_to_process = []

    # Scan src/vibe3/ (excluding services/)
    src_path = Path('src/vibe3')
    for py_file in src_path.rglob('*.py'):
        if 'services' not in py_file.parts and '__pycache__' not in py_file.parts:
            files_to_process.append(py_file)

    # Scan tests/vibe3/ (excluding services/)
    test_path = Path('tests/vibe3')
    for py_file in test_path.rglob('*.py'):
        if 'services' not in py_file.parts and '__pycache__' not in py_file.parts:
            files_to_process.append(py_file)

    print(f"\nFound {len(files_to_process)} files to process")

    # Process each file
    modified_count = 0
    error_count = 0
    errors = []

    for file_path in files_to_process:
        was_modified, error = refactor_file(file_path)
        if error:
            error_count += 1
            errors.append((file_path, error))
            print(f"  ✗ {file_path}: {error}")
        elif was_modified:
            modified_count += 1
            print(f"  ✓ {file_path}")

    print(f"\n" + "=" * 80)
    print(f"SUMMARY")
    print("=" * 80)
    print(f"Files processed: {len(files_to_process)}")
    print(f"Files modified: {modified_count}")
    print(f"Errors: {error_count}")

    if errors:
        print(f"\nERRORS:")
        for file_path, error in errors:
            print(f"  {file_path}: {error}")


if __name__ == '__main__':
    main()
