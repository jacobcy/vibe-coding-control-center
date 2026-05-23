#!/usr/bin/env python3
"""Add @trace_method decorators to Service and Client classes.

Prerequisites:
    - trace_method import already added (use add_trace_imports.py first)

Usage:
    uv run python scripts/add_trace_decorators.py --dry-run  # Preview
    uv run python scripts/add_trace_decorators.py            # Execute
"""

import argparse
import re
from pathlib import Path


def add_decorators_to_file(file_path: Path, layer: str) -> list[str]:
    """Add trace decorators to methods in Service/Client classes.

    Args:
        file_path: Python file path
        layer: Layer name ("service" or "client")

    Returns:
        Modified file lines
    """
    content = file_path.read_text()
    lines = content.split("\n")

    new_lines = []
    i = 0

    # Define valid class name suffixes by layer
    valid_suffixes = {
        "service": ["Service", "Usecase"],
        "client": ["Client"],
    }[layer]

    while i < len(lines):
        line = lines[i]

        # Detect class definition
        class_match = re.match(r'^class (\w+)', line)
        if class_match:
            class_name = class_match.group(1)

            # Only process matching classes
            is_valid_class = any(class_name.endswith(suffix) for suffix in valid_suffixes)

            new_lines.append(line)
            i += 1

            # Process class body
            while i < len(lines):
                current_line = lines[i]

                # Detect method definition
                method_match = re.match(r'^(\s*)def (\w+)\(', current_line)
                if method_match and is_valid_class:
                    indent = method_match.group(1)
                    method_name = method_match.group(2)

                    # Skip if already has decorator
                    if i > 0 and lines[i - 1].strip().startswith('@'):
                        new_lines.append(current_line)
                        i += 1
                        continue

                    # Skip private methods
                    if method_name.startswith('_'):
                        new_lines.append(current_line)
                        i += 1
                        continue

                    # Add decorator
                    trace_name = f"{class_name}.{method_name}"
                    new_lines.append(f'{indent}@trace_method("{trace_name}", layer="{layer}")')

                new_lines.append(current_line)
                i += 1

                # Exit class body at next class
                if re.match(r'^class \w+', current_line):
                    break

            continue

        new_lines.append(line)
        i += 1

    return new_lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Add trace decorators")
    parser.add_argument("--dry-run", action="store_true", help="Preview only")
    args = parser.parse_args()

    base_path = Path(__file__).parent.parent / "src" / "vibe3"

    targets = [
        (base_path / "services", "service"),
        (base_path / "clients", "client"),
    ]

    for target_dir, layer in targets:
        if not target_dir.exists():
            continue

        for py_file in target_dir.glob("*.py"):
            if py_file.name in ["__init__.py", "protocols.py"]:
                continue

            new_lines = add_decorators_to_file(py_file, layer)

            if args.dry_run:
                # Show sample changes
                content = py_file.read_text()
                if "@trace_method" not in content:
                    print(f"Would modify: {py_file.relative_to(base_path)}")
                    # Show first method that would get decorator
                    for i, (old, new) in enumerate(zip(content.split("\n"), new_lines)):
                        if old != new and "@trace_method" in new:
                            print(f"  - {old}")
                            print(f"  + {new}")
                            if i + 1 < len(new_lines):
                                print(f"  + {new_lines[i + 1]}")
                            break
            else:
                new_content = "\n".join(new_lines)
                py_file.write_text(new_content)
                print(f"✓ {py_file.relative_to(base_path)}")


if __name__ == "__main__":
    main()
