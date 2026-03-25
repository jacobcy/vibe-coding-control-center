"""Common execution models for codeagent-wrapper command flows."""

from dataclasses import dataclass

from vibe3.models.review_runner import ReviewAgentOptions, ReviewAgentResult


@dataclass(frozen=True)
class AgentExecutionRequest:
    """Request payload for a shared codeagent-wrapper execution."""

    prompt_file_content: str
    options: ReviewAgentOptions
    task: str | None = None
    dry_run: bool = False
    session_id: str | None = None


@dataclass(frozen=True)
class AgentExecutionOutcome:
    """Result payload for shared execution with resolved session id."""

    result: ReviewAgentResult
    effective_session_id: str | None
