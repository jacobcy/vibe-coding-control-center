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
