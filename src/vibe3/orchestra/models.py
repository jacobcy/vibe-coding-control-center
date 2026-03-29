"""Orchestra data models."""

from pydantic import BaseModel, Field

from vibe3.models.orchestration import IssueState


class IssueInfo(BaseModel):
    """GitHub issue information."""

    number: int
    title: str
    state: IssueState | None
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
