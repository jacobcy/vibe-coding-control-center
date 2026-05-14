"""Data models for GitHub Projects v2 API."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectInfo:
    """Immutable container for project metadata."""

    project_id: str
    status_field_id: str
    status_options: dict[str, str]


@dataclass(frozen=True)
class Item:
    """Immutable container for project item data."""

    item_id: str
    content: dict
    status: str | None
