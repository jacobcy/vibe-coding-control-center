#!/usr/bin/env python3
"""Audit cleanup: trace a decision issue back to source materials and delete them.

Usage:
    # List files that would be deleted (dry-run, default)
    uv run python scripts/audit-cleanup.py --issue 1234

    # Delete files
    uv run python scripts/audit-cleanup.py --issue 1234 --delete

    # Show verbose output
    uv run python scripts/audit-cleanup.py --issue 1234 --verbose

The script traces the ID chain:
    decision issue → source report + linked_observation_ids + linked_suggestion_ids
        → grep .git/shared/observations/ for matching YAML files
        → grep .git/shared/suggestions/ for matching YAML files
        → delete only the explicitly referenced report when available
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple


class MatchedFiles(NamedTuple):
    observations: list[Path]
    suggestions: list[Path]
    reports: list[Path]


def parse_yaml_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a Markdown file.

    Returns empty dict if no frontmatter found or parse error.
    """
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    try:
        import yaml

        return yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}


def parse_simple_list(value: str) -> list[str]:
    """Parse a Markdown-style list into a Python list of strings.

    Handles formats like:
        - obs-20260623T123456-abcdef12
        - obs-20260623T134567-bcdef234
    """
    ids: list[str] = []
    for line in value.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- "):
            ids.append(stripped[2:].strip().strip('"').strip("'"))
        elif stripped.startswith("-"):
            ids.append(stripped[1:].strip().strip('"').strip("'"))
    return [i for i in ids if i]


def extract_ids_from_issue_body(body: str) -> tuple[list[str], list[str]]:
    """Extract linked_observation_ids and linked_suggestion_ids from issue body.

    Searches for patterns like:
        - obs-20260623T123456-abcdef12: [symptom]
        - sug-20260623T140000-fedcba43: [hypothesis]
    """
    obs_ids: list[str] = []
    sug_ids: list[str] = []

    # Match observation IDs (obs-<timestamp>-<hash>)
    obs_pattern = re.compile(r"(obs-\d{8}T\d{6}-[a-f0-9]{8})")
    sug_pattern = re.compile(r"(sug-\d{8}T\d{6}-[a-f0-9]{8})")

    obs_ids = list(set(obs_pattern.findall(body)))
    sug_ids = list(set(sug_pattern.findall(body)))

    return obs_ids, sug_ids


def extract_report_refs_from_issue_body(body: str) -> list[str]:
    """Extract explicitly referenced audit report filenames from issue body."""
    report_pattern = re.compile(r"(audit-report-\d{8}T\d{6}\.md)")
    return list(dict.fromkeys(report_pattern.findall(body)))


def fetch_issue_body(issue_number: int) -> str:
    """Fetch issue body from GitHub via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_number), "--json", "body"],
            capture_output=True,
            text=True,
            check=True,
        )
        import json

        data = json.loads(result.stdout)
        return data.get("body", "")
    except subprocess.CalledProcessError as e:
        print(f"Error fetching issue #{issue_number}: {e.stderr}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing gh output: {e}", file=sys.stderr)
        sys.exit(1)


def find_matching_files(
    shared_dir: Path,
    obs_ids: list[str],
    sug_ids: list[str],
    *,
    report_refs: list[str] | None = None,
    verbose: bool = False,
) -> MatchedFiles:
    """Find all files in shared directory matching the given IDs.

    Strategy:
        - observations/: glob *.yaml, grep content for observation IDs
        - suggestions/: glob *.yaml, grep content for suggestion IDs
        - reports/: prefer explicit report refs from the decision issue body
        - reports fallback: parse frontmatter for both ID types when no report ref
    """
    matched_obs: list[Path] = []
    matched_sug: list[Path] = []
    matched_reports: list[Path] = []

    # Match observation files
    obs_dir = shared_dir / "observations"
    if obs_dir.exists() and obs_ids:
        for obs_file in sorted(obs_dir.glob("audit-observation-*.yaml")):
            try:
                content = obs_file.read_text()
                for obs_id in obs_ids:
                    if obs_id in content:
                        matched_obs.append(obs_file)
                        if verbose:
                            print(f"  [obs]  matched: {obs_file.name} (id: {obs_id})")
                        break
            except Exception:
                continue

    # Match suggestion files
    sug_dir = shared_dir / "suggestions"
    if sug_dir.exists() and sug_ids:
        for sug_file in sorted(sug_dir.glob("audit-suggestion-*.yaml")):
            try:
                content = sug_file.read_text()
                for sug_id in sug_ids:
                    if sug_id in content:
                        matched_sug.append(sug_file)
                        if verbose:
                            print(f"  [sug]  matched: {sug_file.name} (id: {sug_id})")
                        break
            except Exception:
                continue

    # Match report files via frontmatter
    reports_dir = shared_dir / "reports"
    if reports_dir.exists():
        if report_refs:
            for report_name in report_refs:
                report_file = reports_dir / report_name
                if report_file.exists():
                    matched_reports.append(report_file)
                    if verbose:
                        print(f"  [report] matched explicit source report: {report_file.name}")
        else:
            for report_file in sorted(reports_dir.glob("audit-report-*.md")):
                try:
                    content = report_file.read_text()
                    fm = parse_yaml_frontmatter(content)

                    linked_obs = fm.get("linked_observation_ids") or []
                    linked_sug = fm.get("linked_suggestion_ids") or []

                    # Fallback for legacy issues that do not record Source report.
                    obs_match = bool(set(linked_obs) & set(obs_ids)) if obs_ids else False
                    sug_match = bool(set(linked_sug) & set(sug_ids)) if sug_ids else False

                    if obs_match or sug_match:
                        matched_reports.append(report_file)
                        if verbose:
                            print(
                                f"  [report] matched legacy fallback: {report_file.name} "
                                f"(obs={obs_match}, sug={sug_match})"
                            )
                except Exception:
                    continue

    return MatchedFiles(
        observations=matched_obs,
        suggestions=matched_sug,
        reports=matched_reports,
    )


def delete_files(files: Sequence[Path], verbose: bool = False) -> int:
    """Delete the given files. Returns count of deleted files."""
    count = 0
    for f in files:
        try:
            f.unlink()
            if verbose:
                print(f"  deleted: {f}")
            count += 1
        except Exception as e:
            print(f"  error deleting {f}: {e}", file=sys.stderr)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trace a decision issue back to source materials and clean up"
    )
    parser.add_argument(
        "--issue", "-i", type=int, required=True, help="Decision issue number"
    )
    parser.add_argument(
        "--delete", action="store_true", help="Delete matched files (default: dry-run)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose output"
    )
    parser.add_argument(
        "--shared-dir",
        type=Path,
        help="Path to .git/shared/ directory (auto-detected if omitted)",
    )
    args = parser.parse_args()

    # Auto-detect shared directory
    if args.shared_dir:
        shared_dir = args.shared_dir
    else:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-common-dir"],
                capture_output=True,
                text=True,
                check=True,
            )
            shared_dir = Path(result.stdout.strip()) / "shared"
        except subprocess.CalledProcessError:
            shared_dir = Path(".git/shared")

    if not shared_dir.exists():
        print(f"Shared directory not found: {shared_dir}", file=sys.stderr)
        sys.exit(1)

    # Fetch issue body and extract IDs
    print(f"Fetching issue #{args.issue}...")
    body = fetch_issue_body(args.issue)
    obs_ids, sug_ids = extract_ids_from_issue_body(body)
    report_refs = extract_report_refs_from_issue_body(body)

    if not obs_ids and not sug_ids and not report_refs:
        print("No linked observation, suggestion, or report refs found in issue body")
        sys.exit(0)

    print(
        "Found "
        f"{len(obs_ids)} observation IDs, "
        f"{len(sug_ids)} suggestion IDs, "
        f"{len(report_refs)} report refs"
    )

    if args.verbose:
        for oid in obs_ids:
            print(f"  obs_id: {oid}")
        for sid in sug_ids:
            print(f"  sug_id: {sid}")
        for report_ref in report_refs:
            print(f"  report_ref: {report_ref}")

    # Find matching files
    print(f"\nSearching {shared_dir} ...")
    matched = find_matching_files(
        shared_dir,
        obs_ids,
        sug_ids,
        report_refs=report_refs,
        verbose=args.verbose,
    )

    total = len(matched.observations) + len(matched.suggestions) + len(matched.reports)

    if total == 0:
        print("\nNo matching files found. Nothing to clean up.")
        sys.exit(0)

    # Print summary
    print(f"\n{'=== DRY RUN ===' if not args.delete else '=== DELETE ==='}")
    print(f"Observations to {'delete' if args.delete else 'remove'}: {len(matched.observations)}")
    for f in matched.observations:
        print(f"  {f}")
    print(f"Suggestions to {'delete' if args.delete else 'remove'}: {len(matched.suggestions)}")
    for f in matched.suggestions:
        print(f"  {f}")
    print(f"Reports to {'delete' if args.delete else 'remove'}: {len(matched.reports)}")
    for f in matched.reports:
        print(f"  {f}")
    print(f"\nTotal: {total} files")

    if args.delete:
        print()
        deleted = (
            delete_files(matched.observations, verbose=args.verbose)
            + delete_files(matched.suggestions, verbose=args.verbose)
            + delete_files(matched.reports, verbose=args.verbose)
        )
        print(f"Deleted {deleted} files.")
    else:
        print("\nDRY RUN — no files deleted. Use --delete to actually delete.")


if __name__ == "__main__":
    main()
