"""Plan context builder - assemble prompt body for planning agent.

Public API:
- ``build_plan_prompt_body(request, config)`` - assemble the full plan prompt string
- ``make_plan_context_builder(request, config)`` - PromptContextBuilder (via assembler)

Section builders (build_plan_policy_section, etc.) remain available for direct use.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.exceptions import VibeError
from vibe3.models.plan import PlanRequest
from vibe3.prompts.context_builder import PromptContextBuilder, make_context_builder


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


def build_plan_prompt_body(
    request: PlanRequest,
    config: VibeConfig | None = None,
) -> str:
    """Assemble the plan prompt body from policy, tools guide, task, and output format.

    Args:
        request: PlanRequest with scope and task guidance.
        config: VibeConfig instance.

    Returns:
        Assembled plan prompt body string.
    """
    from vibe3.agents.review_prompt import build_tools_guide_section

    log = logger.bind(domain="plan_context_builder", action="build_plan_prompt_body")
    log.info("Building plan prompt body")

    if config is None:
        config = VibeConfig.get_defaults()

    sections: list[str] = []

    plan_config = getattr(config, "plan", None)

    if plan_config and hasattr(plan_config, "policy_file"):
        policy = build_plan_policy_section(plan_config.policy_file)
        if policy:
            sections.append(policy)

    tools_guide = build_tools_guide_section(getattr(plan_config, "common_rules", None))
    if tools_guide:
        sections.append(tools_guide)

    plan_task_text = None
    if plan_config and hasattr(plan_config, "plan_task"):
        plan_task_text = plan_config.plan_task
    task = build_plan_task_section(request, plan_task_text)
    sections.append(task)

    output_format = None
    if plan_config and hasattr(plan_config, "output_format"):
        output_format = plan_config.output_format
    output_contract = build_plan_output_contract_section(output_format)
    sections.append(output_contract)

    body = "\n\n---\n\n".join(sections)
    log.bind(body_len=len(body)).success("Plan prompt body built")
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
