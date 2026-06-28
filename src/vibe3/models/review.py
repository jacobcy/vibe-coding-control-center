"""Review data models - Unified models for review pipeline contract.

This module defines the core data structures for the review pipeline:
- ReviewScope: identifies what is being reviewed (base branch)
- ReviewRequest: encapsulates all information needed for a review

These models enforce contract stability and prevent parameter drift.
"""

from dataclasses import dataclass
from typing import Literal

from vibe3.models.inspect_evidence import ReviewObservation


@dataclass(frozen=True)
class ReviewScope:
    """Identifies what is being reviewed.

    Attributes:
        kind: Type of review - "base" for branch comparison
        base_branch: Base branch to compare against (required if kind="base")

    Examples:
        >>> scope = ReviewScope.for_base("origin/main")
        >>> scope.kind
        'base'
        >>> scope.base_branch
        'origin/main'
    """

    kind: Literal["base"]
    base_branch: str | None = None

    def __post_init__(self) -> None:
        """Validate scope has required fields based on kind."""
        if self.kind == "base" and not self.base_branch:
            raise ValueError("base scope requires base_branch")

    @classmethod
    def for_base(cls, base_branch: str = "origin/main") -> "ReviewScope":
        """Create a scope for reviewing branch changes.

        Args:
            base_branch: Base branch to compare against (default: origin/main)

        Returns:
            ReviewScope with kind="base"
        """
        return cls(kind="base", base_branch=base_branch)


@dataclass(frozen=True)
class ReviewRequest:
    """Encapsulates all information needed for a code review.

    This model unifies the review pipeline contract by:
    - Consolidating scope, exact observation, and task guidance into one object
    - Making the contract explicit and type-safe
    - Enabling future extension (e.g., cloud review, review ready)

    Attributes:
        scope: What is being reviewed (base branch or PR)
        observation: Exact Git and Review Kernel evidence
        task_guidance: Optional custom task instructions

    Examples:
        >>> scope = ReviewScope.for_base("main")
        >>> request = ReviewRequest(scope=scope, task_guidance="Focus on security")
        >>> request.scope.kind
        'base'
        >>> request.task_guidance
        'Focus on security'
    """

    scope: ReviewScope
    observation: ReviewObservation | None = None
    task_guidance: str | None = None
