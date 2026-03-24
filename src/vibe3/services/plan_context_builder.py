"""Plan context builder - Build context for planning agent.

This module constructs stable prompt format for the planning agent
through composable section builders.
"""

from pathlib import Path

from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.exceptions import VibeError
from vibe3.models.plan import PlanRequest


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
        return f"## Planning Task\n{task_text}"

    scope_info = ""
    if request.scope.kind == "task" and request.scope.issue_number:
        scope_info = f"\n- Issue: #{request.scope.issue_number}"
    elif request.scope.kind == "spec" and request.scope.description:
        return f"""## Specification

{request.scope.description}

## Planning Task
- Create a step-by-step implementation plan based on the specification
- Identify dependencies between steps
- Estimate effort for each step
- Flag potential risks or blockers
- Maximum {request.max_steps} steps"""

    return f"""## Planning Task
- Create a step-by-step implementation plan
- Identify dependencies between steps
- Estimate effort for each step
- Flag potential risks or blockers
- Maximum {request.max_steps} steps{scope_info}"""


def build_plan_output_contract_section(output_format: str | None) -> str:
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


def build_plan_context(
    request: PlanRequest,
    config: VibeConfig | None = None,
) -> str:
    """Build plan context from request and configuration."""
    from vibe3.services.context_builder import (
        build_tools_guide_section,
    )

    log = logger.bind(domain="plan_context_builder", action="build_plan_context")
    log.info("Building plan context")

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

    context = "\n\n---\n\n".join(sections)
    log.bind(context_len=len(context)).success("Plan context built")
    return context
