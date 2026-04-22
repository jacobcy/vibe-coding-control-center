"""Run context builder - assemble prompt body for execution agent.

Public API:
- ``build_run_prompt_body(plan_file, config, audit_file, mode)``
- ``make_run_context_builder(plan_file, config, prompts_path, audit_file, mode)``
- ``make_skill_context_builder(skill_content)``
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.prompts.context_builder import PromptContextBuilder, make_context_builder


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


def build_run_standard_sections(config: VibeConfig) -> list[str]:
    """Run role-level hard-standard sections. All run paths must include these.

    Includes: policy_file, common_rules, output_format, run_task (common contract).
    Does NOT include path-specific content (plan, audit, skill, coding_task).
    """
    from vibe3.agents.review_prompt import build_tools_guide_section

    sections: list[str] = []
    run_config = getattr(config, "run", None)

    # Policy file
    if run_config and hasattr(run_config, "policy_file"):
        policy_path = run_config.policy_file
        if policy_path and Path(policy_path).exists():
            sections.append(Path(policy_path).read_text(encoding="utf-8"))

    # Common rules (shared conventions)
    tools_guide = build_tools_guide_section(getattr(run_config, "common_rules", None))
    if tools_guide:
        sections.append(tools_guide)

    # Output format (hard standard — placed before task so task is the LAST section)
    output_format = getattr(run_config, "output_format", None) if run_config else None
    sections.append(build_run_output_contract_section(output_format))

    # Run task (hard standard: includes label-writing instruction — MUST be last)
    run_task = getattr(run_config, "run_task", None) if run_config else None
    sections.append(build_run_task_section(run_task))

    return sections


RunPromptMode = Literal["coding", "fix"]


def build_run_mode_sections(config: VibeConfig, mode: RunPromptMode) -> list[str]:
    """Mode-specific execution sections.

    Injected ONLY for non-skill executor paths.
    - ``coding``: regular implementation round
    - ``fix``: focused retry/fix round based on prior audit feedback
    NOT included in skill/commit paths to avoid instruction conflicts.
    """
    run_config = getattr(config, "run", None)
    if not run_config:
        return []

    section_text: str | None
    if mode == "fix":
        section_text = getattr(run_config, "fix_task", None) or getattr(
            run_config, "coding_task", None
        )
    else:
        section_text = getattr(run_config, "coding_task", None)

    if not section_text:
        return []
    return [section_text]


def build_run_prompt_body(
    plan_file: str | None,
    config: VibeConfig | None = None,
    audit_file: str | None = None,
    mode: RunPromptMode = "coding",
) -> str:
    """Assemble the run prompt body from policy, tools guide, plan, and output format.

    Args:
        plan_file: Path to plan file (markdown), or None for lightweight mode.
        config: VibeConfig instance.
        audit_file: Path to previous review audit file. When provided, the run
            is a retry — review feedback is injected into the prompt so the
            executor addresses the issues found by the reviewer.
        mode: Prompt mode for executor routing. ``coding`` is the default
            implementation path; ``fix`` is a focused repair path.

    Returns:
        Assembled prompt body string.
    """
    if config is None:
        config = VibeConfig.get_defaults()

    log = logger.bind(domain="run_context_builder", action="build_run_prompt_body")
    retry = bool(audit_file)
    log.info(f"Building run prompt body (retry={retry}, mode={mode})")

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

    # Mode-specific guidance (not for skill/commit paths)
    sections.extend(build_run_mode_sections(config, mode))

    # Run role hard-standard sections (shared with all run paths)
    sections.extend(build_run_standard_sections(config))

    body = "\n\n---\n\n".join(sections)
    log.bind(body_len=len(body), retry=retry, mode=mode).success(
        "Run prompt body built"
    )
    return body


def make_run_context_builder(
    plan_file: str | None,
    config: VibeConfig | None = None,
    prompts_path: Path | None = None,
    audit_file: str | None = None,
    mode: RunPromptMode = "coding",
) -> PromptContextBuilder:
    """Create a PromptContextBuilder for plan/flow_plan/lightweight run mode.

    The returned callable routes through PromptAssembler with template key
    ``run.plan`` and a single provider that calls ``build_run_prompt_body``.
    """
    cfg = config or VibeConfig.get_defaults()
    return make_context_builder(
        template_key="run.plan",
        body_provider_key="run.context",
        body_fn=lambda: build_run_prompt_body(plan_file, cfg, audit_file, mode),
        prompts_path=prompts_path,
    )


def make_skill_context_builder(
    skill_content: str,
    config: VibeConfig | None = None,
    prompts_path: Path | None = None,
) -> PromptContextBuilder:
    """Create a PromptContextBuilder for skill execution mode.

    Uses build_run_standard_sections() so the skill agent receives the common
    contract (output_format, run_task exit step, policy, common_rules).
    coding_task is intentionally excluded — skills define their own execution guidance.
    """
    cfg = config or VibeConfig.get_defaults()

    def build() -> str:
        all_sections = [skill_content] + build_run_standard_sections(cfg)
        return "\n\n---\n\n".join(s for s in all_sections if s)

    return make_context_builder(
        template_key="run.skill",
        body_provider_key="run.context",
        body_fn=build,
        prompts_path=prompts_path,
        variable_name="skill_content",
    )
