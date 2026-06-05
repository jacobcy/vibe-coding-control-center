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
  sections (re-exported from prompts.sections)
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

from __future__ import annotations

from typing import TYPE_CHECKING

# Cross-module imports (not self-references) - kept minimal per modularity rules
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
    from vibe3.prompts.sections import build_tools_guide_section


# Lazy imports for self-references (avoid circular init dependencies)
_LAZY_IMPORTS = {
    "CodeagentBackend": "vibe3.agents.backends.codeagent",
    "sync_models_json": "vibe3.agents.backends.codeagent_config",
    "AgentBackend": "vibe3.agents.base",
    "CodeagentCommand": "vibe3.agents.models",
    "CodeagentResult": "vibe3.agents.models",
    "ExecutionRole": "vibe3.agents.models",
    "create_codeagent_command": "vibe3.agents.models",
    "build_plan_prompt_body": "vibe3.agents.plan_prompt",
    "describe_plan_sections": "vibe3.agents.plan_prompt",
    "make_plan_context_builder": "vibe3.agents.plan_prompt",
    "build_snapshot_diff": "vibe3.agents.review_pipeline_helpers",
    "run_inspect_json": "vibe3.agents.review_pipeline_helpers",
    "build_review_prompt_body": "vibe3.agents.review_prompt",
    "describe_review_sections": "vibe3.agents.review_prompt",
    "make_review_context_builder": "vibe3.agents.review_prompt",
    "RunPromptMode": "vibe3.agents.run_prompt",
    "build_run_prompt_body": "vibe3.agents.run_prompt",
    "describe_run_plan_sections": "vibe3.agents.run_prompt",
    "make_publish_context_builder": "vibe3.agents.run_prompt",
    "make_run_context_builder": "vibe3.agents.run_prompt",
    "make_skill_context_builder": "vibe3.agents.run_prompt",
    "build_tools_guide_section": "vibe3.prompts.sections",
}


def __getattr__(name: str) -> object:
    """Lazy import for agents symbols to avoid circular dependencies."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(module, name)
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
