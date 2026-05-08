"""Utilities for issue reference parsing and flow-name task inference."""

import re


def parse_issue_number(issue: str) -> int:
    """Parse issue number from '#123', '123', or GitHub issue URL."""
    digits = issue.removeprefix("#")
    if digits.isdigit():
        return int(digits)
    match = re.search(r"github\.com/[^/]+/[^/]+/issues/(\d+)", issue)
    if match:
        return int(match.group(1))
    raise ValueError(f"Invalid issue format: {issue}")


def try_parse_issue_number(issue: str) -> int | None:
    """Try to parse issue number, returning None on failure."""
    try:
        return parse_issue_number(issue)
    except ValueError:
        return None
