#!/usr/bin/env python3
"""Debug tool to inspect review context without running the agent."""

import json
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vibe3.commands.review_helpers import run_inspect_json
from vibe3.services.context_builder import build_review_context
from vibe3.clients.git_client import GitClient
from vibe3.models.change_source import BranchSource
from vibe3.utils.git_helpers import get_current_branch


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

    # Get git diff
    print("Getting git diff...", file=sys.stderr)
    current_branch = get_current_branch()
    git = GitClient()
    diff = git.get_diff(BranchSource(branch=current_branch, base=args.base))

    # Build impact info
    impact_info = {
        "core_files": inspect_data.get("core_files", []),
        "total_changed": inspect_data.get("total_changed", 0),
        "core_changed": inspect_data.get("core_changed", 0),
    }

    # Build DAG info
    dag_info = None
    impacted_modules = inspect_data.get("impacted_modules", [])
    if impacted_modules:
        assert isinstance(impacted_modules, list)
        dag_info = {
            "impacted_modules": impacted_modules,
            "total_impacted": len(impacted_modules),
        }

    # Build context
    print("Building context...", file=sys.stderr)
    context = build_review_context(
        diff=diff,
        impact=json.dumps(impact_info, indent=2),
        dag=json.dumps(dag_info, indent=2) if dag_info else None,
        score=json.dumps(inspect_data.get("score"), indent=2),
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
    print(f"Diff size: {len(diff)} chars", file=sys.stderr)
    print(f"Impact info: {len(json.dumps(impact_info))} chars", file=sys.stderr)
    print(f"Core files: {len(impact_info['core_files'])}", file=sys.stderr)
    print(f"Total changed: {impact_info['total_changed']}", file=sys.stderr)
    if dag_info:
        print(f"Impacted modules: {dag_info['total_impacted']}", file=sys.stderr)


if __name__ == "__main__":
    main()