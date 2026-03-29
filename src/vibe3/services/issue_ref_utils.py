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


def infer_task_issue_from_flow_name(name: str) -> int | None:
    """Infer issue number from supported flow-name shorthand patterns."""
    patterns = (
        r"^(?:issue|task)[-_]?(\d+)$",
        r"^task/(\d+)$",
        r"^task/(?:issue|task)[-_]?(\d+)$",
    )
    for pattern in patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None
