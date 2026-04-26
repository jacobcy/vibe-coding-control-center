"""Verdict data model for handoff chain."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class VerdictRecord(BaseModel):
    """Verdict record for handoff chain.

    A verdict represents an agent's judgment about the state of a flow.
    It is written by agents (reviewer, manager) and read by downstream
    agents (executor, manager) to understand what action to take.

    The verdict system follows the principle of "tools, not decisions":
    - The tool layer (this model, commands, services) only records and displays
    - The agent layer (prompts) makes decisions based on the verdict data
    """

    verdict: Literal["PASS", "MAJOR", "BLOCK", "UNKNOWN"]
    actor: str  # e.g., "claude/claude-sonnet-4-6"
    role: str  # e.g., "reviewer" | "manager"
    timestamp: datetime
    reason: str | None = None
    issues: str | None = None  # Free text, no structured requirements

    # Association
    flow_branch: str

    def to_handoff_markdown(self) -> str:
        """Convert to handoff update block format.

        Returns:
            Markdown-formatted string for handoff file
        """
        lines = [f"verdict: {self.verdict}"]
        if self.reason:
            lines.append(f"reason: {self.reason}")
        if self.issues:
            lines.append(f"issues: {self.issues}")
        return "\n".join(lines)
