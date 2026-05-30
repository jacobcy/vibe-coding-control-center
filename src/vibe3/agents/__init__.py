"""Agent backend package.

Public API:

Protocols & Models:
- ``AgentBackend`` — protocol that all agent backends must implement
- ``AgentResult`` — dataclass for agent execution result
- ``CodeagentCommand`` — dataclass for codeagent execution configuration
- ``CodeagentResult`` — dataclass for codeagent execution result
- ``ExecutionRole`` — literal type for execution roles
  (planner/executor/reviewer/manager)
- ``RunPromptMode`` — literal type for run prompt mode (coding/retry)

Backend:
- ``CodeagentBackend`` — concrete backend implementation via codeagent-wrapper
- ``AsyncExecutionHandle`` — async execution handle returned by
  ``start_async_command``
- ``start_async_command`` — spawn async agent execution in tmux
- ``resolve_effective_agent_options`` — resolve agent options from
  env/config/defaults
- ``sync_models_json`` — sync models.json before execution
- ``find_missing_backend_commands`` — find missing backend CLI commands

Prompt Builders:
- ``build_plan_prompt_body`` / ``make_plan_context_builder`` — plan agent
  prompt construction
- ``build_run_prompt_body`` / ``make_run_context_builder`` /
  ``make_skill_context_builder`` — run agent prompt construction
- ``build_review_prompt_body`` / ``make_review_context_builder`` — review
  agent prompt construction
- ``build_tools_guide_section`` — shared utility for building tools guide
  sections
- ``describe_plan_sections`` / ``describe_run_plan_sections`` /
  ``describe_review_sections`` — section key inspectors for dry-run summaries

Review Helpers:
- ``run_inspect_json`` — call inspect subcommand and return parsed JSON result
- ``build_snapshot_diff`` — build snapshot diff for review context

Factory:
- ``create_codeagent_command`` — factory function for creating CodeagentCommand

Types:
- ``PromptContextMode`` — literal type for prompt context mode
  (bootstrap/resume)
"""

from vibe3.agents.backends import (
    AsyncExecutionHandle,
    CodeagentBackend,
    find_missing_backend_commands,
    resolve_effective_agent_options,
    start_async_command,
    sync_models_json,
)
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
    make_run_context_builder,
    make_skill_context_builder,
)
from vibe3.models.prompt_meta import PromptContextMode
from vibe3.models.review_runner import AgentResult

__all__ = [
    # Protocols & Models
    "AgentBackend",
    "AgentResult",
    "CodeagentCommand",
    "CodeagentResult",
    "ExecutionRole",
    "RunPromptMode",
    # Backend
    "CodeagentBackend",
    "AsyncExecutionHandle",
    "start_async_command",
    "resolve_effective_agent_options",
    "sync_models_json",
    "find_missing_backend_commands",
    # Prompt Builders
    "build_plan_prompt_body",
    "make_plan_context_builder",
    "build_run_prompt_body",
    "make_run_context_builder",
    "make_skill_context_builder",
    "build_review_prompt_body",
    "make_review_context_builder",
    "build_tools_guide_section",
    "describe_plan_sections",
    "describe_run_plan_sections",
    "describe_review_sections",
    # Review Helpers
    "run_inspect_json",
    "build_snapshot_diff",
    # Factory
    "create_codeagent_command",
    # Types
    "PromptContextMode",
]
