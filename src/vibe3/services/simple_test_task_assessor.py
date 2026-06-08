"""Simple test task assessment service.

Provides heuristic and diff-based assessment functions to identify simple test tasks
that can be routed to the supervisor/apply fast track instead of the full
manager plan→run→review cycle.
"""

from __future__ import annotations

MAX_FILES = 5
MAX_LINES = 100

# Test file path patterns
_TEST_PATTERNS = (
    "tests/",
    "test_",
    "_test.py",
    "conftest.py",
)

# Title keywords indicating test-only tasks
_TEST_TITLE_KEYWORDS = (
    "test",
    "测试",
    "flaky",
    "coverage",
    "mock",
    "fixture",
    "conftest",
    "pytest",
)


def _is_test_file(filepath: str) -> bool:
    """Check if file path matches test file patterns.

    Args:
        filepath: File path to check

    Returns:
        True if file path matches test patterns, False otherwise
    """
    return any(p in filepath for p in _TEST_PATTERNS)


def is_simple_test_task_from_metadata(title: str, labels: list[str]) -> bool:
    """Heuristic: is this issue likely a simple test task?

    Conservative assessment based on issue metadata. Only returns True when:
    - Title clearly indicates test-only work
    - No labels suggest complexity

    Args:
        title: Issue title
        labels: List of issue labels

    Returns:
        True if issue is likely a simple test task, False otherwise
    """
    title_lower = title.lower()

    # Must have test-related keyword in title
    if not any(kw in title_lower for kw in _TEST_TITLE_KEYWORDS):
        return False

    # Exclude if labels suggest complexity
    complex_labels = {"roadmap/epic", "roadmap/rfc", "priority/0", "priority/1"}
    if complex_labels & set(labels):
        return False

    return True


def is_simple_test_from_diff(
    changed_files: list[str],
    additions: int,
    deletions: int,
) -> bool:
    """Diff-based assessment: is this a simple test-only change?

    Args:
        changed_files: List of changed file paths
        additions: Total lines added
        deletions: Total lines deleted

    Returns:
        True if change is simple test-only, False otherwise
    """
    if not changed_files:
        return False
    if len(changed_files) > MAX_FILES:
        return False
    if (additions + deletions) > MAX_LINES:
        return False
    return all(_is_test_file(f) for f in changed_files)
