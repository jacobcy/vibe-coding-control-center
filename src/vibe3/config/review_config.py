"""Review configuration models."""

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Agent configuration for codeagent-wrapper.

    Two mutually exclusive modes:
    1. Use preset: agent (e.g., "code-reviewer")
    2. Direct specification: backend + model (optional)
    """

    agent: str | None = Field(
        default=None,
        description="Agent preset name (e.g., code-reviewer)",
    )
    backend: str | None = Field(
        default=None,
        description="Backend name (e.g., claude, codex)",
    )
    model: str | None = Field(
        default=None,
        description="Model name (optional, e.g., claude-3-opus)",
    )

    def validate_mutually_exclusive(self) -> None:
        """Validate that agent and backend are not both specified."""
        if self.agent and self.backend:
            raise ValueError(
                "agent and backend are mutually exclusive. "
                "Use either agent preset OR backend+model, not both."
            )
