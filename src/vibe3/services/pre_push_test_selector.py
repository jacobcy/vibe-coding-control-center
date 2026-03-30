"""Select pre-push test targets from changed files."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Sequence

SMOKE_TEST_TARGETS = (
    "tests/vibe3/services/test_pre_push_scope.py",
    "tests/vibe3/integration/test_review_shell_contract.py",
)

HOOK_TEST_TARGETS = (
    "tests/vibe3/integration/test_review_shell_contract.py",
    "tests/vibe3/hooks/test_pre_push_review_gate.py",
    "tests/vibe3/test_metrics_hooks_bug_condition.py",
)


@dataclass(frozen=True)
class PrePushTestSelection:
    """Resolved test plan for pre-push."""

    mode: Literal["incremental", "smoke", "full"]
    tests: list[str]
    reason: str
    unmapped_sources: list[str] = field(default_factory=list)


def select_pre_push_tests(
    changed_files: Sequence[str], repo_root: Path | None = None
) -> PrePushTestSelection:
    """Resolve test targets using a safety-first incremental strategy."""
    root = repo_root or Path.cwd()
    selected: set[str] = set()
    unmapped_sources: list[str] = []

    for raw in changed_files:
        rel = raw.strip()
        if not rel:
            continue

        if _is_python_test_path(rel):
            test_path = root / rel
            if test_path.exists():
                selected.add(rel)
            continue

        if rel.startswith("scripts/hooks/"):
            selected.update(_existing_targets(root, HOOK_TEST_TARGETS))
            continue

        if _is_v3_source_path(rel):
            mapped = _map_source_to_tests(rel, root)
            if mapped:
                selected.update(mapped)
            else:
                unmapped_sources.append(rel)

    if unmapped_sources:
        # Layer 2: DAG-based import analysis.
        # Reuses dag_service (same infrastructure as the inspect risk-assessment step)
        # to find which test files transitively import the changed modules.
        # e.g. change check_remote_index_mixin.py (no named test file) →
        #   check_service.py imports it → test_check_service.py imports check_service
        #   → run only those 3 tests instead of the full services directory.
        dag_targets = _find_tests_via_dag(unmapped_sources, root)
        if dag_targets:
            all_targets = selected | dag_targets
            return PrePushTestSelection(
                mode="incremental",
                tests=sorted(all_targets),
                reason="DAG import analysis resolved tests from unmapped sources",
                unmapped_sources=sorted(unmapped_sources),
            )

        # Layer 3: Directory-scoped fallback: run tests in the same subdirectory
        # as the unmapped source files rather than the full suite.
        dir_targets: set[str] = set()
        for src_path in unmapped_sources:
            src_rel = Path(src_path).relative_to("src/vibe3")
            test_dir = root / "tests" / "vibe3" / src_rel.parent
            if test_dir.exists() and any(test_dir.glob("test_*.py")):
                dir_targets.add(test_dir.relative_to(root).as_posix())
        if dir_targets:
            return PrePushTestSelection(
                mode="incremental",
                tests=sorted(dir_targets),
                reason=(
                    "no direct test file mapping, "
                    "scoped to test directory of changed source"
                ),
                unmapped_sources=sorted(unmapped_sources),
            )
        return PrePushTestSelection(
            mode="full",
            tests=["tests/vibe3"],
            reason="source-to-test mapping missing, fallback to full suite",
            unmapped_sources=sorted(unmapped_sources),
        )

    if selected:
        return PrePushTestSelection(
            mode="incremental",
            tests=sorted(selected),
            reason="incremental tests resolved from changed files",
        )

    smoke = _existing_targets(root, SMOKE_TEST_TARGETS)
    if smoke:
        return PrePushTestSelection(
            mode="smoke",
            tests=smoke,
            reason="no direct test targets found, run smoke fallback",
        )

    return PrePushTestSelection(
        mode="full",
        tests=["tests/vibe3"],
        reason="smoke tests unavailable, fallback to full suite",
    )


def _find_tests_via_dag(src_files: list[str], root: Path) -> set[str]:
    """Find test files that transitively import any of the changed source modules.

    Reuses dag_service infrastructure (the same code used for risk assessment in
    the inspect step) to go beyond file-name heuristics:
      1. Build the src import graph and BFS-expand impacted modules from seed files.
      2. Scan test files with the same AST import extractor to find which tests
         actually import any impacted module.

    Returns an empty set on any failure so callers degrade to directory fallback.
    """
    try:
        from vibe3.services.dag_service import (  # noqa: PLC0415
            _extract_imports,
            expand_impacted_modules,
        )
    except ImportError:
        return set()

    try:
        impact = expand_impacted_modules(list(src_files))
        affected = set(impact.impacted_modules)
        if not affected:
            return set()

        test_root = root / "tests" / "vibe3"
        if not test_root.exists():
            return set()

        hits: set[str] = set()
        for test_file in sorted(test_root.glob("**/test_*.py")):
            if "__pycache__" in str(test_file):
                continue
            file_imports = _extract_imports(str(test_file))
            if any(imp in affected for imp in file_imports):
                try:
                    hits.add(test_file.relative_to(root).as_posix())
                except ValueError:
                    pass
        return hits
    except Exception:  # noqa: BLE001
        return set()


def _is_python_test_path(path: str) -> bool:
    return path.startswith("tests/vibe3/") and path.endswith(".py")


def _is_v3_source_path(path: str) -> bool:
    return path.startswith("src/vibe3/") and path.endswith(".py")


def _existing_targets(root: Path, targets: Sequence[str]) -> list[str]:
    return [target for target in targets if (root / target).exists()]


def _map_source_to_tests(source_path: str, root: Path) -> list[str]:
    src = Path(source_path)
    rel = src.relative_to("src/vibe3")
    test_dir = root / "tests" / "vibe3" / rel.parent
    stem = rel.stem

    candidates = [
        test_dir / f"test_{stem}.py",
        test_dir / f"{stem}_test.py",
    ]
    candidates.extend(sorted(test_dir.glob(f"test_{stem}*.py")))
    candidates.extend(sorted(test_dir.glob(f"*{stem}*.py")))

    resolved: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.exists():
            rel_path = candidate.relative_to(root).as_posix()
            if rel_path not in seen:
                seen.add(rel_path)
                resolved.append(rel_path)
    return resolved


def main() -> None:
    """Read changed files from stdin and print test selection JSON."""
    changed_files = [line.strip() for line in sys.stdin.readlines() if line.strip()]
    selection = select_pre_push_tests(changed_files)
    print(json.dumps(asdict(selection)))


if __name__ == "__main__":
    main()
