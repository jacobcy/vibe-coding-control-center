"""Helper functions for plan command."""

from typing import Literal

from vibe3.config.settings import VibeConfig
from vibe3.models.review_runner import AgentOptions
from vibe3.services.codeagent_execution_service import CodeagentExecutionService


def get_agent_options(
    config: VibeConfig,
    agent: str | None,
    backend: str | None,
    model: str | None,
    section: Literal["plan", "run"] = "plan",
) -> AgentOptions:
    """Build agent options with CLI override support."""
    if section not in {"plan", "run"}:
        raise ValueError(f"Unsupported section: {section}")
    return CodeagentExecutionService(config).resolve_agent_options(
        section=section,
        agent=agent,
        backend=backend,
        model=model,
    )
