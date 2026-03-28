"""Orchestra data models."""

from datetime import datetime

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


class Trigger(BaseModel):
    """A trigger for executing a command."""

    issue: IssueInfo
    from_state: IssueState | None
    to_state: IssueState
    command: str
    args: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def trigger_key(self) -> str:
        """Unique key for this trigger."""
        from_str = self.from_state.value if self.from_state else "none"
        return f"{from_str}->{self.to_state.value}"
