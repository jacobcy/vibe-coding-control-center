"""Shared change-scope utilities for hooks and inspect pipelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from loguru import logger

if TYPE_CHECKING:
    from vibe3.models.change_source import ChangeSource
    from vibe3.services.serena_service import SerenaService


@dataclass(frozen=True)
class ChangedFileScope:
    """Classified changed-file view used across hook/inspect flows."""

    all_files: list[str]
    existing_files: list[str]
    deleted_files: list[str]
    test_files: list[str]
    v3_source_files: list[str]
    v3_test_files: list[str]
    hook_files: list[str]
    other_files: list[str]


def is_test_file(filepath: str) -> bool:
    """Return True when a path is considered a test file."""
    return (
        filepath.startswith(("tests/", "test_", "test/"))
        or "/tests/" in filepath
        or "/test/" in filepath
        or filepath.endswith("_test.py")
    )


def is_v3_source_file(filepath: str) -> bool:
    """Return True for Python source under src/vibe3."""
    return filepath.startswith("src/vibe3/") and filepath.endswith(".py")


def is_v3_test_file(filepath: str) -> bool:
    """Return True for Python tests under tests/vibe3."""
    return filepath.startswith("tests/vibe3/") and filepath.endswith(".py")


def is_hook_file(filepath: str) -> bool:
    """Return True for shell hooks."""
    return filepath.startswith("scripts/hooks/")


def classify_changed_files(
    changed_files: Sequence[str], repo_root: Path | None = None
) -> ChangedFileScope:
    """Classify changed files once for reuse across pipelines."""
    root = repo_root or Path.cwd()
    all_files = [path.strip() for path in changed_files if path and path.strip()]

    existing_files: list[str] = []
    deleted_files: list[str] = []
    test_files: list[str] = []
    v3_source_files: list[str] = []
    v3_test_files: list[str] = []
    hook_files: list[str] = []
    other_files: list[str] = []

    for rel in all_files:
        if (root / rel).exists():
            existing_files.append(rel)
        else:
            deleted_files.append(rel)

        if is_test_file(rel):
            test_files.append(rel)
        if is_v3_source_file(rel):
            v3_source_files.append(rel)
        if is_v3_test_file(rel):
            v3_test_files.append(rel)
        if is_hook_file(rel):
            hook_files.append(rel)
        if not (is_test_file(rel) or is_v3_source_file(rel) or is_hook_file(rel)):
            other_files.append(rel)

    return ChangedFileScope(
        all_files=all_files,
        existing_files=existing_files,
        deleted_files=deleted_files,
        test_files=test_files,
        v3_source_files=v3_source_files,
        v3_test_files=v3_test_files,
        hook_files=hook_files,
        other_files=other_files,
    )


def count_changed_lines(
    diff_text: str,
    code_paths: Sequence[str] | None = None,
) -> int:
    """Count changed (+/-) lines from a git diff string."""
    changed_lines = 0
    current_file: str | None = None

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split()
            current_file = parts[2][2:] if len(parts) >= 4 else None
            continue

        if not current_file:
            continue

        if code_paths and not any(
            current_file.startswith(path.rstrip("/")) for path in code_paths
        ):
            continue

        if (
            line.startswith(("+", "-"))
            and not line.startswith("+++")
            and not line.startswith("---")
        ):
            changed_lines += 1

    return changed_lines


def collect_changed_symbols(
    serena_service: "SerenaService",
    source: "ChangeSource",
    changed_files: Sequence[str],
    fail_fast: bool = False,
) -> tuple[dict[str, list[str]], int]:
    """Extract changed Python symbols while skipping tests."""
    changed_symbols_by_file: dict[str, list[str]] = {}
    skipped_tests = 0

    for file in changed_files:
        if is_test_file(file):
            skipped_tests += 1
            continue
        if not file.endswith(".py"):
            continue

        try:
            changed_funcs = serena_service.get_changed_functions(file, source=source)
        except Exception as error:  # noqa: BLE001
            if fail_fast:
                raise
            logger.debug(f"Skipping symbol extraction for {file}: {error}")
            continue

        if changed_funcs:
            changed_symbols_by_file[file] = changed_funcs

    return changed_symbols_by_file, skipped_tests
