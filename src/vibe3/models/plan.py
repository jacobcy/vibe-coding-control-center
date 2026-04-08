"""Plan data models - Unified models for plan pipeline contract."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class PlanScope:
    """Identifies what is being planned.

    Attributes:
        kind: Type of plan - "task" for issue-based, "spec" for specification-based
        issue_number: GitHub issue number (required if kind="task")
        description: Specification content (required if kind="spec")
    """

    kind: Literal["task", "spec"]
    issue_number: int | None = None
    description: str | None = None

    def __post_init__(self) -> None:
        """Validate scope has required fields based on kind."""
        if self.kind == "task" and self.issue_number is None:
            raise ValueError("task scope requires issue_number")
        if self.kind == "spec" and not self.description:
            raise ValueError("spec scope requires description")

    @classmethod
    def for_task(cls, issue_number: int) -> "PlanScope":
        """Create a scope for planning an issue task."""
        return cls(kind="task", issue_number=issue_number)

    @classmethod
    def for_spec(cls, description: str) -> "PlanScope":
        """Create a scope for planning from specification."""
        return cls(kind="spec", description=description)


@dataclass(frozen=True)
class PlanRequest:
    """Encapsulates all information needed for planning.

    Attributes:
        scope: What is being planned
        task_guidance: Optional custom planning instructions
        max_steps: Maximum number of steps in the plan (default: 10)
    """

    scope: PlanScope
    task_guidance: str | None = None
    max_steps: int = 10


@dataclass
class PlanTaskInput:
    """Resolved inputs for task planning."""

    issue_number: int
    branch: str
    request: PlanRequest
    used_flow_issue: bool = False


@dataclass
class PlanSpecInput:
    """Resolved inputs for spec planning."""

    branch: str
    request: PlanRequest
    description: str
    spec_path: str | None = None
