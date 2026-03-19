#!/usr/bin/env python3
"""Debug tool to inspect review context without running the agent."""

import json
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vibe3.commands.review_helpers import run_inspect_json
from vibe3.services.context_builder import build_review_context


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Show review context for debugging"
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base branch to compare against (default: origin/main)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file (default: stdout)",
    )
    parser.add_argument(
        "--sections",
        action="store_true",
        help="Show section breakdown",
    )
    args = parser.parse_args()

    print(f"Building review context for base: {args.base}", file=sys.stderr)

    # Get inspect data
    print("Running inspect base...", file=sys.stderr)
    inspect_data = run_inspect_json(["base", args.base])

    # Extract AST-level analysis
    changed_symbols = inspect_data.get("changed_symbols", {})

    # Build context with AST analysis
    print("Building context...", file=sys.stderr)
    context = build_review_context(
        changed_symbols=changed_symbols if changed_symbols else None,
    )

    # Output
    output_file = args.output
    if output_file:
        Path(output_file).write_text(context, encoding="utf-8")
        print(f"Context written to: {output_file}", file=sys.stderr)
    else:
        print(context)

    # Section breakdown
    if args.sections:
        print("\n=== Section Breakdown ===", file=sys.stderr)
        sections = context.split("\n\n---\n\n")
        for i, section in enumerate(sections, 1):
            # Extract section title
            lines = section.strip().split("\n")
            title = lines[0] if lines else f"Section {i}"
            print(
                f"{i}. {title[:60]}... ({len(section)} chars)",
                file=sys.stderr,
            )

    # Summary stats
    print("\n=== Stats ===", file=sys.stderr)
    print(f"Total context size: {len(context)} chars", file=sys.stderr)
    print(f"Impact info: {len(json.dumps(impact_info))} chars", file=sys.stderr)
    print(f"Core files: {len(impact_info['core_files'])}", file=sys.stderr)
    print(f"Total changed: {impact_info['total_changed']}", file=sys.stderr)
    if dag_info:
        print(f"Impacted modules: {dag_info['total_impacted']}", file=sys.stderr)


if __name__ == "__main__":
    main()