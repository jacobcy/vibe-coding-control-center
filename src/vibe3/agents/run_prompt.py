"""Run context builder - assemble prompt body for execution agent.

Public API:
- ``build_run_prompt_body(plan_file, config, audit_file)``
  assemble the full prompt string
- ``make_run_context_builder(plan_file, config, prompts_path, audit_file)``
  returns a PromptContextBuilder
- ``make_skill_context_builder(skill_content)``
  PromptContextBuilder for skill mode
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.context_builder import PromptContextBuilder, make_context_builder
from vibe3.prompts.models import (
    PromptRecipe,
    PromptVariableSource,
    VariableSourceKind,
)
from vibe3.prompts.provider_registry import ProviderRegistry


def build_run_task_section(task_text: str | None) -> str:
    """Build execution task section."""
    if task_text:
        return f"## Execution Task\n{task_text}"

    return """## Execution Task

- Execute the implementation plan
- Make the necessary code changes
- Ensure changes compile and pass tests
- Output a report of changes made"""


def build_run_output_contract_section(output_format: str | None) -> str:
    """Build execution output contract section."""
    if output_format:
        return "## Output format requirements\n" f"{output_format}"

    return """## Output format requirements

You MUST output a structured report in this EXACT format at the END of your response,
no matter what. Do not include this section in your response until the very end.

## Changes Made
### Modified Files
- [file path 1]: [brief description of changes]
- [file path 2]: [brief description of changes]
- ... (list EVERY file you modified, created, or deleted)

### Summary
[1-2 sentence summary of what was accomplished]

### Verification
- [X] Code compiles (if applicable)
- [X] All existing tests pass
- [X] No breaking changes introduced
- [X] Changes follow coding standards
"""


def build_run_prompt_body(
    plan_file: str | None,
    config: VibeConfig | None = None,
    audit_file: str | None = None,
) -> str:
    """Assemble the run prompt body from policy, tools guide, plan, and output format.

    Args:
        plan_file: Path to plan file (markdown), or None for lightweight mode.
        config: VibeConfig instance.
        audit_file: Path to previous review audit file. When provided, the run
            is a retry — review feedback is injected into the prompt so the
            executor addresses the issues found by the reviewer.

    Returns:
        Assembled prompt body string.
    """
    if config is None:
        config = VibeConfig.get_defaults()

    log = logger.bind(domain="run_context_builder", action="build_run_prompt_body")
    retry = bool(audit_file)
    log.info(f"Building run prompt body (retry={retry})")

    plan_content = None
    if plan_file:
        if not Path(plan_file).exists():
            raise FileNotFoundError(f"Plan file not found: {plan_file}")
        plan_content = Path(plan_file).read_text(encoding="utf-8")

    audit_content: str | None = None
    if audit_file:
        audit_path = Path(audit_file)
        if audit_path.exists():
            audit_content = audit_path.read_text(encoding="utf-8")
        else:
            log.warning(f"Audit file not found: {audit_file}")

    sections: list[str] = []

    run_config = getattr(config, "run", None)
    if run_config and hasattr(run_config, "policy_file"):
        policy_path = run_config.policy_file
        if policy_path and Path(policy_path).exists():
            sections.append(Path(policy_path).read_text(encoding="utf-8"))

    from vibe3.agents.review_prompt import build_tools_guide_section

    tools_guide = build_tools_guide_section(getattr(run_config, "common_rules", None))
    if tools_guide:
        sections.append(tools_guide)

    if plan_content:
        sections.append(f"## Implementation Plan\n\n{plan_content}")

    # Retry mode: inject review feedback so executor addresses prior issues
    if audit_content:
        sections.append(
            "## Previous Review Feedback (RETRY)\n\n"
            "The previous implementation was reviewed and issues were found. "
            "You MUST address the feedback below before producing new output.\n\n"
            f"{audit_content}"
        )

    run_task = getattr(run_config, "run_task", None) if run_config else None
    sections.append(build_run_task_section(run_task))

    output_format = getattr(run_config, "output_format", None) if run_config else None
    sections.append(build_run_output_contract_section(output_format))

    body = "\n\n---\n\n".join(sections)
    log.bind(body_len=len(body), retry=retry).success("Run prompt body built")
    return body


def make_run_context_builder(
    plan_file: str | None,
    config: VibeConfig | None = None,
    prompts_path: Path | None = None,
    audit_file: str | None = None,
) -> PromptContextBuilder:
    """Create a PromptContextBuilder for plan/flow_plan/lightweight run mode.

    The returned callable routes through PromptAssembler with template key
    ``run.plan`` and a single provider that calls ``build_run_prompt_body``.
    """
    cfg = config or VibeConfig.get_defaults()
    return make_context_builder(
        template_key="run.plan",
        body_provider_key="run.context",
        body_fn=lambda: build_run_prompt_body(plan_file, cfg, audit_file),
        prompts_path=prompts_path,
    )


def make_skill_context_builder(
    skill_content: str,
    prompts_path: Path | None = None,
) -> PromptContextBuilder:
    """Create a PromptContextBuilder for skill execution mode.

    The returned callable routes through PromptAssembler with template key
    ``run.skill`` and a LITERAL source for ``skill_content``.
    """
    recipe = PromptRecipe(
        template_key="run.skill",
        variables={
            "skill_content": PromptVariableSource(
                kind=VariableSourceKind.LITERAL,
                value=skill_content,
            )
        },
    )
    registry = ProviderRegistry()
    assembler = PromptAssembler(prompts_path=prompts_path, registry=registry)
    return PromptContextBuilder(assembler, recipe)
