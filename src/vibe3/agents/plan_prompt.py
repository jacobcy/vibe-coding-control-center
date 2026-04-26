"""Plan context builder - assemble prompt body for planning agent.

Public API:
- ``build_plan_prompt_body(request, config)`` - assemble the full plan prompt string
- ``make_plan_context_builder(request, config)`` - PromptContextBuilder (via assembler)

Section builders (build_plan_policy_section, etc.) remain available for direct use.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.exceptions import VibeError
from vibe3.execution.prompt_meta import PromptContextMode
from vibe3.models.plan import PlanRequest
from vibe3.prompts.context_builder import PromptContextBuilder, make_context_builder
from vibe3.prompts.manifest import PromptManifest, PromptProvider

PlanPromptMode = Literal["first", "retry"]


class PlanContextBuilderError(VibeError):
    """Plan context build failed."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Plan context build failed: {details}", recoverable=False)


def build_plan_policy_section(policy_path: str | None) -> str | None:
    """Build plan policy section from file."""
    if not policy_path:
        return None

    log = logger.bind(domain="plan_context_builder", action="build_plan_policy_section")
    path = Path(policy_path)
    if not path.exists():
        return None

    try:
        content = path.read_text(encoding="utf-8")
        log.success("Plan policy section built")
        return content
    except OSError as e:
        log.bind(error=str(e), path=str(policy_path)).warning(
            "Could not read plan policy"
        )
        return None


def build_plan_task_section(
    request: PlanRequest,
    task_text: str | None,
) -> str:
    """Build plan task section."""
    if task_text:
        if request.task_guidance:
            return f"## Planning Task\n{task_text}\n\n{request.task_guidance}"
        return f"## Planning Task\n{task_text}"

    scope_info = ""
    if request.scope.kind == "task" and request.scope.issue_number:
        scope_info = f"\n- Issue: #{request.scope.issue_number}"
    elif request.scope.kind == "spec" and request.scope.description:
        section = f"""## Specification

{request.scope.description}

## Planning Task

- Create a step-by-step implementation plan based on the specification
- Identify dependencies between steps
- Estimate effort for each step
- Flag potential risks or blockers
- Maximum {request.max_steps} steps"""
        if request.task_guidance:
            section += f"\n\n{request.task_guidance}"
        return section

    section = f"""## Planning Task

- Create a step-by-step implementation plan
- Identify dependencies between steps
- Estimate effort for each step
- Flag potential risks or blockers
- Maximum {request.max_steps} steps{scope_info}"""
    if request.task_guidance:
        section += f"\n\n{request.task_guidance}"
    return section


def build_plan_output_contract_section(output_format: str | None) -> str:
    """Build plan output contract section."""
    if output_format:
        return "## Output format requirements\n" f"{output_format}"

    return """## Output format requirements

Output a structured plan in this format:

## Plan Summary
[1-2 sentence overview]

## Steps
1. [Step description]
   - Files: [list of files to modify]
   - Effort: [S/M/L]
   - Dependencies: [step numbers or "none"]

2. [Step description]
   - Files: [list of files to modify]
   - Effort: [S/M/L]
   - Dependencies: [step numbers or "none"]

## Risks
- [Risk description]

## Notes
[Optional additional context]"""


def _plan_variant(mode: PlanPromptMode, context_mode: PromptContextMode) -> str:
    if context_mode == "resume":
        return f"{mode}.resume"
    return f"{mode}.bootstrap"


def describe_plan_sections(
    mode: PlanPromptMode,
    context_mode: PromptContextMode,
) -> list[str]:
    """Return configured plan.default section keys for dry-run summaries."""
    variant = _plan_variant(mode, context_mode)
    return list(
        PromptManifest.load_default().recipe("plan.default").variant(variant).sections
    )


def _build_plan_prompt_providers(
    request: PlanRequest,
    config: VibeConfig,
    context_mode: PromptContextMode,
) -> dict[str, PromptProvider]:
    """Build providers used by config/prompt-recipes.yaml plan sections."""
    from vibe3.agents.review_prompt import build_tools_guide_section

    plan_config = getattr(config, "plan", None)
    task_request = (
        request if context_mode == "bootstrap" else PlanRequest(scope=request.scope)
    )

    def plan_policy() -> str | None:
        if not plan_config or not hasattr(plan_config, "policy_file"):
            return None
        return build_plan_policy_section(plan_config.policy_file)

    def plan_output_format() -> str:
        output_format = (
            getattr(plan_config, "output_format", None) if plan_config else None
        )
        return build_plan_output_contract_section(output_format)

    def plan_retry_task() -> str | None:
        return getattr(plan_config, "retry_task", None) if plan_config else None

    def plan_exit_contract() -> str:
        plan_task_text = (
            getattr(plan_config, "plan_task", None) if plan_config else None
        )
        return build_plan_task_section(task_request, plan_task_text)

    return {
        "plan.policy": plan_policy,
        "common.rules": lambda: build_tools_guide_section(
            getattr(plan_config, "common_rules", None)
        ),
        "plan.output_format": plan_output_format,
        "plan.retry_task": plan_retry_task,
        "plan.exit_contract": plan_exit_contract,
        # Backward-compatible alias for local recipe overrides.
        "plan.task": plan_exit_contract,
    }


def build_plan_prompt_body(
    request: PlanRequest,
    config: VibeConfig | None = None,
    mode: PlanPromptMode = "first",
    context_mode: PromptContextMode = "bootstrap",
) -> str:
    """Assemble the plan prompt body from policy, tools guide, task, and output format.

    Args:
        request: PlanRequest with scope and task guidance.
        config: VibeConfig instance.
        mode: Prompt mode. ``retry`` revises an existing plan.
        context_mode: ``resume`` means an existing session is available, so use
            the minimal retry prompt instead of re-sending policy/rules context.

    Returns:
        Assembled plan prompt body string.
    """
    log = logger.bind(
        domain="plan_context_builder",
        action="build_plan_prompt_body",
        prompt_mode=mode,
        context_mode=context_mode,
    )
    log.info("Building plan prompt body")

    if config is None:
        config = VibeConfig.get_defaults()

    body = PromptManifest.load_default().render_sections(
        recipe_key="plan.default",
        variant_key=_plan_variant(mode, context_mode),
        providers=_build_plan_prompt_providers(request, config, context_mode),
    )
    log.bind(body_len=len(body), prompt_mode=mode, context_mode=context_mode).success(
        "Plan prompt body built"
    )
    return body


def make_plan_context_builder(
    request: PlanRequest,
    config: VibeConfig | None = None,
    prompts_path: Path | None = None,
) -> PromptContextBuilder:
    """Create a PromptContextBuilder for the plan command.

    Routes through PromptAssembler with template key ``plan.default``
    and a single provider that calls ``build_plan_prompt_body``.
    """
    cfg = config or VibeConfig.get_defaults()
    return make_context_builder(
        template_key="plan.default",
        body_provider_key="plan.context",
        body_fn=lambda: build_plan_prompt_body(request, cfg),
        prompts_path=prompts_path,
    )
