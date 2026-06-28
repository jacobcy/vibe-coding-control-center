"""Select pre-push test targets from changed files."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Sequence

from vibe3.analysis.change_scope_service import classify_changed_files

SMOKE_TEST_TARGETS = (
    "tests/vibe3/analysis/test_pre_push_scope.py",
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

    mode: Literal["incremental", "smoke", "full", "skip"]
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

    scope = classify_changed_files(changed_files, repo_root=root)

    for test_path in scope.v3_test_files:
        if (root / test_path).exists():
            selected.add(test_path)

    if scope.hook_files:
        selected.update(_existing_targets(root, HOOK_TEST_TARGETS))

    for src_path in scope.v3_source_files:
        mapped = _map_source_to_tests(src_path, root)
        if mapped:
            selected.update(mapped)
        else:
            unmapped_sources.append(src_path)

    if unmapped_sources:
        # Directory-scoped fallback: run tests in the same subdirectory
        # as the unmapped source files rather than the full suite.
        dir_targets: set[str] = set()
        from vibe3.config import get_source_root

        src_root = get_source_root()
        for src_path in unmapped_sources:
            src_rel = Path(src_path).relative_to(src_root)
            test_dir = root / "tests" / "vibe3" / src_rel.parent
            if test_dir.exists() and any(test_dir.glob("test_*.py")):
                dir_targets.add(test_dir.relative_to(root).as_posix())
        # Guard: if any resolved directory is the full test suite root,
        # skip local pytest instead of running everything.
        if "tests/vibe3" in dir_targets:
            return PrePushTestSelection(
                mode="skip",
                tests=[],
                reason=(
                    f"unmapped source(s) resolve to full test suite root, "
                    f"skipping local run (CI covers full suite): "
                    f"{', '.join(sorted(unmapped_sources))}"
                ),
                unmapped_sources=sorted(unmapped_sources),
            )
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
            mode="skip",
            tests=[],
            reason=(
                "no test directory for changed source, "
                "skipping local run (CI covers full suite)"
            ),
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
        mode="skip",
        tests=[],
        reason="no applicable test targets, skipping local run (CI covers full suite)",
    )


def _existing_targets(root: Path, targets: Sequence[str]) -> list[str]:
    return [target for target in targets if (root / target).exists()]


def _map_source_to_tests(source_path: str, root: Path) -> list[str]:
    from vibe3.config import get_source_root

    src = Path(source_path)
    src_root = get_source_root()
    rel = src.relative_to(src_root)
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
        # __init__.py files contain no tests; skip to avoid "no tests ran" warnings
        if candidate.name == "__init__.py":
            continue
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
