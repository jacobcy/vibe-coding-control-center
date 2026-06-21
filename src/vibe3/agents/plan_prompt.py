"""Plan context builder - assemble prompt body for planning agent.

Public API:
- ``build_plan_prompt_body(request, config)`` - assemble the full plan prompt string
- ``make_plan_context_builder(request, config)`` - PromptContextBuilder (via assembler)
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from loguru import logger

from vibe3.config import VibeConfig, get_resolver
from vibe3.models import PlanRequest, PromptContextMode
from vibe3.prompts import (
    PromptContextBuilder,
    PromptManifest,
    PromptProvider,
    build_common_rules_section,
    build_policy_section,
    build_project_common_rules_section,
    make_context_builder,
)

PlanPromptMode = Literal["first", "retry"]


def _build_plan_task_section(
    request: PlanRequest,
) -> str:
    """Build plan task guidance section (no exit contract content)."""
    if request.task_guidance:
        return request.task_guidance

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


def _build_plan_exit_contract_section(task_text: str | None) -> str | None:
    """Build plan exit contract section — static role contract only."""
    if task_text:
        return f"## Planner Exit Contract\n{task_text}"
    return None


def _build_plan_output_contract_section(output_format: str | None) -> str:
    """Build plan output contract section."""
    if output_format:
        return f"## Output format requirements\n{output_format}"

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
    prompts_path: Path | None = None,
) -> list[str]:
    """Return configured plan.default section keys for dry-run summaries."""
    variant = _plan_variant(mode, context_mode)
    manifest = PromptManifest.load_for_prompts_path(prompts_path)
    return list(manifest.recipe("plan.default").variant(variant).sections)


def _build_plan_prompt_providers(
    request: PlanRequest,
    config: VibeConfig,
    context_mode: PromptContextMode,
) -> dict[str, PromptProvider]:
    """Build providers used by config/prompts/prompt-recipes.yaml plan sections."""
    plan_config = getattr(config, "plan", None)
    task_request = (
        request if context_mode == "bootstrap" else PlanRequest(scope=request.scope)
    )
    resolver = get_resolver()

    def plan_policy() -> str | None:
        if not plan_config:
            return None
        policy_path = (
            plan_config.policy_file
            if plan_config.policy_file is not None
            else resolver.get_policy_path("plan")
        )
        return build_policy_section(policy_path, "plan")

    def plan_output_format() -> str:
        output_format = (
            getattr(plan_config, "output_format", None) if plan_config else None
        )
        return _build_plan_output_contract_section(output_format)

    def plan_retry_task() -> str | None:
        return getattr(plan_config, "retry_task", None) if plan_config else None

    def plan_exit_contract() -> str | None:
        plan_task_text = (
            getattr(plan_config, "plan_task", None) if plan_config else None
        )
        return _build_plan_exit_contract_section(plan_task_text)

    def plan_task() -> str:
        return _build_plan_task_section(task_request)

    def common_rules_section() -> str | None:
        return build_common_rules_section(
            plan_config.common_rules if plan_config else None, resolver
        )

    def project_common_rules_section() -> str | None:
        return build_project_common_rules_section()

    return {
        "plan.policy": plan_policy,
        "common.rules": common_rules_section,
        "common.rules@project": project_common_rules_section,
        "plan.output_format": plan_output_format,
        "plan.retry_task": plan_retry_task,
        "plan.exit_contract": plan_exit_contract,
        "plan.task": plan_task,
    }


def build_plan_prompt_body(
    request: PlanRequest,
    config: VibeConfig | None = None,
    mode: PlanPromptMode = "first",
    context_mode: PromptContextMode = "bootstrap",
    prompts_path: Path | None = None,
    annotate_sections: bool = False,
) -> str:
    """Assemble the plan prompt body from policy, tools guide, task, and output format.

    Args:
        request: PlanRequest with scope and task guidance.
        config: VibeConfig instance.
        mode: Prompt mode. ``retry`` revises an existing plan.
        context_mode: ``resume`` means an existing session is available, so use
            the minimal retry prompt instead of re-sending policy/rules context.
        prompts_path: Optional custom path to prompts.yaml. When provided,
            loads the prompt-recipes.yaml from the same directory.
        annotate_sections: When True, wrap each section with markers.

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

    if prompts_path is not None:
        manifest = PromptManifest.load(prompts_path.parent / "prompt-recipes.yaml")
    else:
        manifest = PromptManifest.load_default()
    body = manifest.render_sections(
        recipe_key="plan.default",
        variant_key=_plan_variant(mode, context_mode),
        providers=_build_plan_prompt_providers(request, config, context_mode),
        annotate_sections=annotate_sections,
    )
    log.bind(body_len=len(body)).success("Plan prompt body built")
    return body


def make_plan_context_builder(
    request: PlanRequest,
    config: VibeConfig | None = None,
    prompts_path: Path | None = None,
    annotate_sections: bool = False,
) -> PromptContextBuilder:
    """Create a PromptContextBuilder for the plan command.

    Routes through PromptAssembler with template key ``plan.default``
    and a single provider that calls ``build_plan_prompt_body``.
    """
    cfg = config or VibeConfig.get_defaults()
    return make_context_builder(
        template_key="plan.default",
        body_provider_key="plan.context",
        body_fn=lambda: build_plan_prompt_body(
            request, cfg, prompts_path=prompts_path, annotate_sections=annotate_sections
        ),
        prompts_path=prompts_path,
    )
