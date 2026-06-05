"""Agent backend package.

Public API:

Protocols & Models:
- ``AgentBackend`` — protocol that all agent backends must implement
- ``CodeagentCommand`` — dataclass for codeagent execution configuration
- ``CodeagentResult`` — dataclass for codeagent execution result
- ``create_codeagent_command`` — factory function for codeagent execution commands
- ``ExecutionRole`` — literal type for execution roles
  (planner/executor/reviewer/manager)

Backend:
- ``CodeagentBackend`` — concrete backend implementation via codeagent-wrapper

Prompt Builders:
- ``build_plan_prompt_body`` / ``make_plan_context_builder`` — plan agent
  prompt construction
- ``build_run_prompt_body`` / ``make_run_context_builder`` /
  ``make_skill_context_builder`` / ``make_publish_context_builder`` — run
  agent prompt construction
- ``build_review_prompt_body`` / ``make_review_context_builder`` — review
  agent prompt construction
- ``build_tools_guide_section`` — shared utility for building tools guide
  sections
- ``describe_plan_sections`` / ``describe_run_plan_sections`` /
  ``describe_review_sections`` — section key inspectors for dry-run summaries

Review Helpers:
- ``build_snapshot_diff`` — build structural diff for review context
- ``run_inspect_json`` — helper to call inspect subcommand for review analysis

Types:
- ``PromptContextMode`` — literal type for prompt context mode
  (bootstrap/resume)
- ``RunPromptMode`` — literal type for run prompt mode (coding/retry)

Backend Config:
- ``sync_models_json`` — sync effective backend/model settings to
  ``~/.codeagent/models.json``
"""

from typing import TYPE_CHECKING, Any

from vibe3.models import PromptContextMode

if TYPE_CHECKING:
    from vibe3.agents.backends.codeagent import CodeagentBackend
    from vibe3.agents.backends.codeagent_config import sync_models_json
    from vibe3.agents.base import AgentBackend
    from vibe3.agents.models import (
        CodeagentCommand,
        CodeagentResult,
        ExecutionRole,
        create_codeagent_command,
    )
    from vibe3.agents.plan_prompt import (
        build_plan_prompt_body,
        describe_plan_sections,
        make_plan_context_builder,
    )
    from vibe3.agents.review_pipeline_helpers import (
        build_snapshot_diff,
        run_inspect_json,
    )
    from vibe3.agents.review_prompt import (
        build_review_prompt_body,
        build_tools_guide_section,
        describe_review_sections,
        make_review_context_builder,
    )
    from vibe3.agents.run_prompt import (
        RunPromptMode,
        build_run_prompt_body,
        describe_run_plan_sections,
        make_publish_context_builder,
        make_run_context_builder,
        make_skill_context_builder,
    )


def __getattr__(name: str) -> Any:
    """Lazy import for all symbols to avoid circular dependencies."""
    if name == "CodeagentBackend":
        from vibe3.agents.backends.codeagent import CodeagentBackend

        return CodeagentBackend
    if name == "sync_models_json":
        from vibe3.agents.backends.codeagent_config import sync_models_json

        return sync_models_json
    if name == "AgentBackend":
        from vibe3.agents.base import AgentBackend

        return AgentBackend
    if name == "CodeagentCommand":
        from vibe3.agents.models import CodeagentCommand

        return CodeagentCommand
    if name == "CodeagentResult":
        from vibe3.agents.models import CodeagentResult

        return CodeagentResult
    if name == "ExecutionRole":
        from vibe3.agents.models import ExecutionRole

        return ExecutionRole
    if name == "create_codeagent_command":
        from vibe3.agents.models import create_codeagent_command

        return create_codeagent_command
    if name == "build_plan_prompt_body":
        from vibe3.agents.plan_prompt import build_plan_prompt_body

        return build_plan_prompt_body
    if name == "describe_plan_sections":
        from vibe3.agents.plan_prompt import describe_plan_sections

        return describe_plan_sections
    if name == "make_plan_context_builder":
        from vibe3.agents.plan_prompt import make_plan_context_builder

        return make_plan_context_builder
    if name == "build_snapshot_diff":
        from vibe3.agents.review_pipeline_helpers import build_snapshot_diff

        return build_snapshot_diff
    if name == "run_inspect_json":
        from vibe3.agents.review_pipeline_helpers import run_inspect_json

        return run_inspect_json
    if name == "build_review_prompt_body":
        from vibe3.agents.review_prompt import build_review_prompt_body

        return build_review_prompt_body
    if name == "build_tools_guide_section":
        from vibe3.agents.review_prompt import build_tools_guide_section

        return build_tools_guide_section
    if name == "describe_review_sections":
        from vibe3.agents.review_prompt import describe_review_sections

        return describe_review_sections
    if name == "make_review_context_builder":
        from vibe3.agents.review_prompt import make_review_context_builder

        return make_review_context_builder
    if name == "RunPromptMode":
        from vibe3.agents.run_prompt import RunPromptMode

        return RunPromptMode
    if name == "build_run_prompt_body":
        from vibe3.agents.run_prompt import build_run_prompt_body

        return build_run_prompt_body
    if name == "describe_run_plan_sections":
        from vibe3.agents.run_prompt import describe_run_plan_sections

        return describe_run_plan_sections
    if name == "make_publish_context_builder":
        from vibe3.agents.run_prompt import make_publish_context_builder

        return make_publish_context_builder
    if name == "make_run_context_builder":
        from vibe3.agents.run_prompt import make_run_context_builder

        return make_run_context_builder
    if name == "make_skill_context_builder":
        from vibe3.agents.run_prompt import make_skill_context_builder

        return make_skill_context_builder

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Protocols & Models
    "AgentBackend",
    "CodeagentCommand",
    "CodeagentResult",
    "create_codeagent_command",
    "ExecutionRole",
    # Backend
    "CodeagentBackend",
    # Prompt Builders
    "build_plan_prompt_body",
    "make_plan_context_builder",
    "build_run_prompt_body",
    "make_run_context_builder",
    "make_skill_context_builder",
    "make_publish_context_builder",
    "build_review_prompt_body",
    "make_review_context_builder",
    "build_tools_guide_section",
    "describe_plan_sections",
    "describe_run_plan_sections",
    "describe_review_sections",
    # Review Helpers
    "build_snapshot_diff",
    "run_inspect_json",
    # Types
    "PromptContextMode",
    "RunPromptMode",
    "sync_models_json",
]
