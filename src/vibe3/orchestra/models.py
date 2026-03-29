"""Orchestra data models."""

from __future__ import annotations

from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from vibe3.models.orchestration import IssueState


class IssueInfo(BaseModel):
    """GitHub issue information."""

    number: int
    title: str
    state: IssueState | None = None
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)  # GitHub login names
    url: str | None = None

    @property
    def slug(self) -> str:
        """Generate slug from title."""
        slug = self.title.lower()
        slug = "".join(c if c.isalnum() or c == "-" else "-" for c in slug)
        while "--" in slug:
            slug = slug.replace("--", "-")
        return slug.strip("-")[:50]

    @classmethod
    def from_github_payload(cls, payload: dict[str, Any]) -> IssueInfo | None:
        """Create IssueInfo from a raw GitHub webhook issue payload.

        Handles both webhook format (with nested ``labels`` objects)
        and list-issues format (flat dicts with ``assignees`` arrays).
        Returns None if the payload cannot be parsed.
        """
        try:
            labels = [lb["name"] for lb in payload.get("labels", [])]

            state = None
            for lb in labels:
                parsed = IssueState.from_label(lb)
                if parsed is not None:
                    state = parsed
                    break

            return cls(
                number=int(payload["number"]),
                title=str(payload.get("title", "")),
                state=state,
                labels=labels,
                assignees=[a["login"] for a in payload.get("assignees", [])],
                url=payload.get("html_url") or payload.get("url"),
            )
        except (KeyError, ValueError) as exc:
            logger.bind(domain="orchestra").warning(
                f"Cannot parse issue payload: {exc}"
            )
            return None
