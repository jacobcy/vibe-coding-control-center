#!/usr/bin/env python3
"""Audit schema validator: validate observation/suggestion/report files.

Usage:
    # Validate all audit artifacts (observations, suggestions, reports)
    uv run python scripts/audit-validate.py --all

    # Validate a specific file
    uv run python scripts/audit-validate.py --file audit-observation-20260626.yaml

    # Validate only observations
    uv run python scripts/audit-validate.py --observations

    # Generate a compliant observation from existing non-compliant data
    uv run python scripts/audit-validate.py --fix obs-20260626-bad.yaml --output audit-observation-20260626.yaml

    # JSON output for machine consumption
    uv run python scripts/audit-validate.py --all --format json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_OBSERVATION_KEYS = [
    "audit_observation",
]
REQUIRED_OBSERVATION_FIELDS = [
    "schema_version",
    "observation_id",
    "created_at",
    "created_by",
    "source_material",
    "subject",
    "observation",
    "facts",
    "interpretation",
    "next_stage_input",
]
REQUIRED_SUBJECT_FIELDS = ["issue_number", "branch", "flow_status"]
REQUIRED_OBSERVATION_SUB_FIELDS = [
    "title",
    "symptom",
    "observed_failure_mode",
    "confidence",
]
VALID_FAILURE_MODES = {
    "scope_mismatch",
    "missing_output",
    "state_loop",
    "contract_missing",
    "ci_failure",
    "review_gap",
    "unknown",
}
VALID_CONFIDENCES = {"high", "medium", "low"}
OBSERVATION_ID_PATTERN = re.compile(r"^obs-\d{8}T\d{6}-[a-f0-9]{8}$")
OBS_FILENAME_PATTERN = re.compile(r"^audit-observation-\d{8}T\d{6}\.ya?ml$")
SUG_FILENAME_PATTERN = re.compile(r"^audit-suggestion-\d{8}T\d{6}-[a-zA-Z0-9_-]+\.ya?ml$")
REPORT_FILENAME_PATTERN = re.compile(r"^audit-report-\d{8}T\d{6}\.md$")


@dataclass
class ValidationError:
    file: str
    severity: str  # "error", "warning"
    field: str
    message: str


@dataclass
class ValidationResult:
    file: str
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    @property
    def has_issues(self) -> bool:
        return len(self.errors) > 0 or len(self.warnings) > 0


def git_common_dir() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            check=True,
            text=True,
            capture_output=True,
        )
        return Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path(".git")


def parse_yaml_file(path: Path) -> dict[str, Any]:
    """Parse a YAML file. Returns empty dict on failure."""
    content = path.read_text(encoding="utf-8")
    try:
        import yaml

        return yaml.safe_load(content) or {}
    except Exception:
        return {}


def validate_observation_file(path: Path) -> ValidationResult:
    """Validate an observation YAML file."""
    result = ValidationResult(file=str(path))

    # Check filename
    if not OBS_FILENAME_PATTERN.match(path.name):
        result.errors.append(
            ValidationError(
                file=str(path),
                severity="error",
                field="filename",
                message=f"Filename must match audit-observation-YYYYMMDDTHHMMSS.yaml, got: {path.name}",
            )
        )

    # Parse and check content
    data = parse_yaml_file(path)
    if not data:
        result.errors.append(
            ValidationError(
                file=str(path),
                severity="error",
                field="content",
                message="File is empty or cannot be parsed as YAML",
            )
        )
        return result

    # Check root key
    if "audit_observation" not in data:
        result.errors.append(
            ValidationError(
                file=str(path),
                severity="error",
                field="root_key",
                message="Missing required root key 'audit_observation:'. File must start with 'audit_observation:' as the top-level YAML key.",
            )
        )
        return result

    obs = data["audit_observation"]
    if not isinstance(obs, dict):
        result.errors.append(
            ValidationError(
                file=str(path),
                severity="error",
                field="root_value",
                message="'audit_observation:' must be a mapping, not a scalar or list",
            )
        )
        return result

    # Check required top-level fields
    for field_name in REQUIRED_OBSERVATION_FIELDS:
        if field_name not in obs:
            result.errors.append(
                ValidationError(
                    file=str(path),
                    severity="error",
                    field=field_name,
                    message=f"Missing required field: audit_observation.{field_name}",
                )
            )

    # Validate observation_id format
    obs_id = obs.get("observation_id", "")
    if obs_id and not OBSERVATION_ID_PATTERN.match(str(obs_id)):
        result.warnings.append(
            ValidationError(
                file=str(path),
                severity="warning",
                field="observation_id",
                message=f"observation_id '{obs_id}' does not match pattern obs-YYYYMMDDTHHMMSS-XXXXXXXX",
            )
        )

    # Validate subject sub-fields
    subject = obs.get("subject", {})
    if isinstance(subject, dict):
        for field_name in REQUIRED_SUBJECT_FIELDS:
            if field_name not in subject:
                result.warnings.append(
                    ValidationError(
                        file=str(path),
                        severity="warning",
                        field=f"subject.{field_name}",
                        message=f"Missing field: audit_observation.subject.{field_name}",
                    )
                )

    # Validate observation sub-fields
    observation = obs.get("observation", {})
    if isinstance(observation, dict):
        for field_name in REQUIRED_OBSERVATION_SUB_FIELDS:
            if field_name not in observation:
                result.warnings.append(
                    ValidationError(
                        file=str(path),
                        severity="warning",
                        field=f"observation.{field_name}",
                        message=f"Missing field: audit_observation.observation.{field_name}",
                    )
                )
        fm = observation.get("observed_failure_mode", "")
        if fm and fm not in VALID_FAILURE_MODES:
            result.warnings.append(
                ValidationError(
                    file=str(path),
                    severity="warning",
                    field="observation.observed_failure_mode",
                    message=f"Unknown failure mode '{fm}'. Valid values: {sorted(VALID_FAILURE_MODES)}",
                )
            )
        conf = observation.get("confidence", "")
        if conf and conf not in VALID_CONFIDENCES:
            result.warnings.append(
                ValidationError(
                    file=str(path),
                    severity="warning",
                    field="observation.confidence",
                    message=f"Invalid confidence '{conf}'. Must be one of: {sorted(VALID_CONFIDENCES)}",
                )
            )

    # Check facts list
    facts = obs.get("facts", [])
    if isinstance(facts, list):
        if len(facts) == 0:
            result.warnings.append(
                ValidationError(
                    file=str(path),
                    severity="warning",
                    field="facts",
                    message="facts list is empty. At least one fact is expected.",
                )
            )
        for i, fact in enumerate(facts):
            if isinstance(fact, dict):
                if "kind" not in fact:
                    result.warnings.append(
                        ValidationError(
                            file=str(path),
                            severity="warning",
                            field=f"facts[{i}].kind",
                            message=f"Fact {i} missing 'kind' field",
                        )
                    )

    # Check interpretation
    interp = obs.get("interpretation", {})
    if isinstance(interp, dict):
        if "reasoning" not in interp:
            result.warnings.append(
                ValidationError(
                    file=str(path),
                    severity="warning",
                    field="interpretation.reasoning",
                    message="Missing interpretation.reasoning",
                )
            )

    # Check for multi-document YAML (common violation)
    content = path.read_text(encoding="utf-8")
    doc_separators = re.findall(r"^---\s*$", content, re.MULTILINE)
    if len(doc_separators) > 0:
        # Check if there's content after the first --- separator
        parts = re.split(r"^---\s*$", content, maxsplit=1, flags=re.MULTILINE)
        if len(parts) > 1 and parts[1].strip():
            result.errors.append(
                ValidationError(
                    file=str(path),
                    severity="error",
                    field="content",
                    message="Multi-document YAML detected. Only one YAML document per file is allowed. audit-ledger-summary.py cannot parse multi-document files.",
                )
            )

    return result


def validate_suggestion_file(path: Path) -> ValidationResult:
    """Validate a suggestion YAML file."""
    result = ValidationResult(file=str(path))

    if not SUG_FILENAME_PATTERN.match(path.name):
        result.warnings.append(
            ValidationError(
                file=str(path),
                severity="warning",
                field="filename",
                message=f"Expected filename pattern audit-suggestion-YYYYMMDDTHHMMSS-<suffix>.yaml, got: {path.name}",
            )
        )

    data = parse_yaml_file(path)
    if not data:
        result.errors.append(
            ValidationError(
                file=str(path),
                severity="error",
                field="content",
                message="File is empty or cannot be parsed as YAML",
            )
        )
        return result

    if "audit_suggestion" not in data:
        result.errors.append(
            ValidationError(
                file=str(path),
                severity="error",
                field="root_key",
                message="Missing required root key 'audit_suggestion:'",
            )
        )
        return result

    sug = data["audit_suggestion"]
    if not isinstance(sug, dict):
        result.errors.append(
            ValidationError(
                file=str(path),
                severity="error",
                field="root_value",
                message="'audit_suggestion:' must be a mapping",
            )
        )
        return result

    required_fields = [
        "suggestion_id",
        "linked_observation_ids",
        "hypothesis",
        "recommended_action",
        "confidence",
    ]
    for field_name in required_fields:
        if field_name not in sug:
            result.errors.append(
                ValidationError(
                    file=str(path),
                    severity="error",
                    field=field_name,
                    message=f"Missing required field: audit_suggestion.{field_name}",
                )
            )

    linked = sug.get("linked_observation_ids", [])
    if isinstance(linked, list) and len(linked) < 2:
        result.warnings.append(
            ValidationError(
                file=str(path),
                severity="warning",
                field="linked_observation_ids",
                message=f"Anti-bloat rule: suggestion should have >= 2 linked observations, got {len(linked)}",
            )
        )

    return result


def validate_report_file(path: Path) -> ValidationResult:
    """Validate a report Markdown file."""
    result = ValidationResult(file=str(path))

    if not REPORT_FILENAME_PATTERN.match(path.name):
        result.warnings.append(
            ValidationError(
                file=str(path),
                severity="warning",
                field="filename",
                message=f"Expected filename pattern audit-report-YYYYMMDDTHHMMSS.md, got: {path.name}",
            )
        )

    content = path.read_text(encoding="utf-8")
    fm = parse_yaml_frontmatter(content)

    if not fm:
        result.errors.append(
            ValidationError(
                file=str(path),
                severity="error",
                field="frontmatter",
                message="Missing YAML frontmatter (--- ... ---). Required for machine-parseable ID chains.",
            )
        )
        return result

    required_frontmatter = [
        "linked_observation_ids",
        "linked_suggestion_ids",
        "evidence_strength",
        "cluster_key",
        "target_materials",
        "created_at",
        "created_by",
    ]
    for field_name in required_frontmatter:
        if field_name not in fm:
            result.errors.append(
                ValidationError(
                    file=str(path),
                    severity="error",
                    field=f"frontmatter.{field_name}",
                    message=f"Missing required frontmatter field: {field_name}",
                )
            )

    valid_strengths = {"strong", "medium", "weak", "inconclusive"}
    es = fm.get("evidence_strength", "")
    if es and es not in valid_strengths:
        result.errors.append(
            ValidationError(
                file=str(path),
                severity="error",
                field="frontmatter.evidence_strength",
                message=f"Invalid evidence_strength '{es}'. Must be: {sorted(valid_strengths)}",
            )
        )

    # Check for required sections
    if "Prompt Material Analysis" not in content:
        result.errors.append(
            ValidationError(
                file=str(path),
                severity="error",
                field="content",
                message="Missing required section 'Prompt Material Analysis'. Report must analyze original prompt materials, not just cluster observations.",
            )
        )

    return result


def parse_yaml_frontmatter(content: str) -> dict[str, Any]:
    """Parse YAML frontmatter from a Markdown file."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        import yaml

        return yaml.safe_load(match.group(1)) or {}
    except Exception:
        return {}


def file_age_days(path: Path) -> int | None:
    """Extract age from filename timestamp. Returns None if unparseable."""
    match = re.search(r"(\d{8}T\d{6})", path.name)
    if not match:
        return None
    try:
        file_ts = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S")
        file_ts = file_ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - file_ts).days
    except ValueError:
        return None


def prune_files(
    shared_dir: Path,
    max_age_days: int = 10,
    dry_run: bool = True,
    verbose: bool = False,
) -> int:
    """Delete non-compliant and expired audit files.

    Deletes:
    1. Files that fail YAML parsing (broken/corrupt)
    2. Files older than max_age_days (stale data)

    Returns count of deleted files.
    """
    import yaml

    files = find_audit_files(shared_dir)
    to_delete: list[tuple[Path, str]] = []  # (path, reason)

    for category, paths in files.items():
        for path in paths:
            # Check 1: YAML parseability (for YAML files)
            if path.suffix in (".yaml", ".yml"):
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8"))
                    if data is None:
                        to_delete.append((path, "empty or unparseable YAML"))
                        continue
                except Exception:
                    to_delete.append((path, "YAML parse error"))
                    continue

                # Check 1b: Multi-document YAML
                content = path.read_text(encoding="utf-8")
                doc_count = len(re.findall(r"^(?:---\s*$|\\.\\.\\.\s*$)", content, re.MULTILINE))
                if doc_count > 1:
                    to_delete.append((path, f"multi-document YAML ({doc_count} docs)"))

            # Check 2: File age
            age = file_age_days(path)
            if age is not None and age > max_age_days:
                to_delete.append((path, f"expired ({age} days old, max {max_age_days})"))

    # Deduplicate (a file might match multiple conditions)
    seen: set[str] = set()
    unique: list[tuple[Path, str]] = []
    for p, reason in to_delete:
        key = str(p)
        if key not in seen:
            seen.add(key)
            unique.append((p, reason))

    if dry_run:
        print(f"\n{'='*60}")
        print(f"PRUNE DRY-RUN — {len(unique)} files would be deleted")
        print(f"{'='*60}")
        for p, reason in unique:
            print(f"  {p.name:50s} {reason}")
        if not unique:
            print("  (nothing to prune)")
        print(f"\nRun with --prune --delete to actually delete.")
    else:
        deleted = 0
        for p, reason in unique:
            try:
                p.unlink()
                if verbose:
                    print(f"  deleted: {p.name} ({reason})")
                deleted += 1
            except Exception as e:
                print(f"  error deleting {p.name}: {e}", file=sys.stderr)
        print(f"\nPruned {deleted} files.")

    return len(unique)


def find_audit_files(shared_dir: Path) -> dict[str, list[Path]]:
    """Find all audit files in the shared directory."""
    files: dict[str, list[Path]] = {
        "observations": [],
        "suggestions": [],
        "reports": [],
    }
    obs_dir = shared_dir / "observations"
    if obs_dir.exists():
        files["observations"] = sorted(obs_dir.glob("audit-observation-*.y*ml"))
        # Also find non-standard named files
        for pattern in ["obs-*.yaml", "obs-*.yml"]:
            files["observations"].extend(sorted(obs_dir.glob(pattern)))

    sug_dir = shared_dir / "suggestions"
    if sug_dir.exists():
        files["suggestions"] = sorted(sug_dir.glob("audit-suggestion-*.y*ml"))

    reports_dir = shared_dir / "reports"
    if reports_dir.exists():
        files["reports"] = sorted(reports_dir.glob("audit-report-*.md"))

    return files


def print_results(
    results: list[ValidationResult], format_type: str = "text"
) -> int:
    """Print validation results. Returns count of errors."""
    total_errors = 0
    total_warnings = 0

    if format_type == "json":
        output = {"files": []}
        for r in results:
            file_result = {
                "file": r.file,
                "valid": r.is_valid,
                "errors": [{"field": e.field, "message": e.message} for e in r.errors],
                "warnings": [
                    {"field": w.field, "message": w.message} for w in r.warnings
                ],
            }
            output["files"].append(file_result)
            total_errors += len(r.errors)
            total_warnings += len(r.warnings)
        output["summary"] = {
            "total_files": len(results),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "all_valid": total_errors == 0,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        for r in results:
            status = "✅ PASS" if r.is_valid else "❌ FAIL"
            print(f"\n{status}  {r.file}")
            for e in r.errors:
                print(f"  ❌ [{e.field}] {e.message}")
                total_errors += 1
            for w in r.warnings:
                print(f"  ⚠️  [{w.field}] {w.message}")
                total_warnings += 1

        print(f"\n{'='*60}")
        print(
            f"Summary: {len(results)} files, {total_errors} errors, {total_warnings} warnings"
        )
        if total_errors == 0:
            print("✅ All files pass validation")
        else:
            print(f"❌ {total_errors} error(s) found — downstream tools may not parse these files")

    return total_errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate audit observation/suggestion/report files"
    )
    parser.add_argument("--all", action="store_true", help="Validate all audit files")
    parser.add_argument("--observations", action="store_true", help="Validate only observations")
    parser.add_argument("--suggestions", action="store_true", help="Validate only suggestions")
    parser.add_argument("--reports", action="store_true", help="Validate only reports")
    parser.add_argument("--file", type=Path, help="Validate a specific file")
    parser.add_argument(
        "--shared-dir",
        type=Path,
        help="Path to .git/shared/ directory (auto-detected if omitted)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Prune non-compliant and expired files (dry-run by default, add --delete to execute)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete files when used with --prune",
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=10,
        help="Max file age in days before pruning (default: 10)",
    )
    args = parser.parse_args()

    shared_dir = args.shared_dir or (git_common_dir() / "shared")

    if args.prune:
        prune_files(
            shared_dir, max_age_days=args.max_age,
            dry_run=not args.delete, verbose=args.delete,
        )
        return

    results: list[ValidationResult] = []

    if args.file:
        path = args.file
        if "observation" in path.name.lower():
            results.append(validate_observation_file(path))
        elif "suggestion" in path.name.lower():
            results.append(validate_suggestion_file(path))
        elif "report" in path.name.lower():
            results.append(validate_report_file(path))
        else:
            print(f"Cannot determine file type for: {path}", file=sys.stderr)
            sys.exit(1)
    else:
        files = find_audit_files(shared_dir)

        if args.all or args.observations:
            for path in files["observations"]:
                results.append(validate_observation_file(path))

        if args.all or args.suggestions:
            for path in files["suggestions"]:
                results.append(validate_suggestion_file(path))

        if args.all or args.reports:
            for path in files["reports"]:
                results.append(validate_report_file(path))

    if not results:
        print("No audit files found to validate.", file=sys.stderr)
        print(f"Shared directory: {shared_dir}", file=sys.stderr)
        sys.exit(0)

    error_count = print_results(results, format_type=args.format)
    sys.exit(min(error_count, 1))


if __name__ == "__main__":
    main()