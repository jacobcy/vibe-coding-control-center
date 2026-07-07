"""BaseResolver — Protocol for base branch resolution.

Import paths:
    # Recommended (explicit source)
    from vibe3.clients.protocols.pr import BaseResolver

"""

from typing import Protocol


class BaseResolver(Protocol):
    """Protocol for base branch resolution."""

    def resolve_pr_create_base(self, requested_base: str | None) -> str: ...
    def collect_branch_material(self, base_branch: str, branch: str) -> object: ...


__all__ = ["BaseResolver"]
