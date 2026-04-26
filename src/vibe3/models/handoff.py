"""Handoff data models."""

from dataclasses import dataclass
from typing import Literal

from vibe3.models.review_runner import AgentOptions

HandoffKind = Literal["plan", "run", "review", "indicate"]


@dataclass(frozen=True)
class HandoffRecord:
    """Generic handoff record for all agent command artifacts."""

    kind: HandoffKind
    content: str
    options: AgentOptions
    session_id: str | None = None
    metadata: dict[str, str] | None = None
    branch: str | None = None
    log_path: str | None = None
