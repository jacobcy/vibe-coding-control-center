"""Label utility functions."""

from __future__ import annotations


def normalize_labels(raw_labels: object) -> list[str]:
    """Extract label names from GitHub issue payload labels field."""
    if not isinstance(raw_labels, list):
        return []
    result: list[str] = []
    for item in raw_labels:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str):
                result.append(name)
    return result
