"""Run context builder - Build context for execution agent.

Reuses plan_context_builder logic but changes:
- Task section: execute the plan
- Output contract: code changes + report
"""

from pathlib import Path

from loguru import logger

from vibe3.config.settings import VibeConfig


def build_run_context(
    plan_file: str | None,
    config: VibeConfig | None = None,
) -> str:
    """Build run context from a plan file.

    Args:
        plan_file: Path to plan file (markdown), or None for lightweight mode
        config: VibeConfig instance

    Returns:
        Complete run context string
    """
    if config is None:
        config = VibeConfig.get_defaults()

    log = logger.bind(domain="run_context_builder", action="build_run_context")
    log.info("Building run context from plan file")

    # Load plan content if provided
    plan_content = None
    if plan_file:
        if not Path(plan_file).exists():
            raise FileNotFoundError(f"Plan file not found: {plan_file}")
        plan_content = Path(plan_file).read_text(encoding="utf-8")

    sections: list[str] = []

    run_config = getattr(config, "run", None)
    if run_config and hasattr(run_config, "policy_file"):
        policy_path = run_config.policy_file
        if policy_path and Path(policy_path).exists():
            sections.append(Path(policy_path).read_text(encoding="utf-8"))

    from vibe3.services.context_builder import build_tools_guide_section

    tools_guide = build_tools_guide_section(getattr(run_config, "common_rules", None))
    if tools_guide:
        sections.append(tools_guide)

    # Add plan content if provided
    if plan_content:
        sections.append(f"## Implementation Plan\n\n{plan_content}")

    sections.append("## Execution Task\n\n- Execute the implementation plan\n- Make the necessary code changes\n- Ensure changes compile and pass tests\n- Output a report of changes made")

    # Use output_format from config or default
    if run_config and hasattr(run_config, "output_format"):
        output_format = run_config.output_format
    else:
        # Default format for backward compatibility
        output_format = """## Output format requirements

You MUST output a structured report in this EXACT format at the END of your response, no matter what. Do not include this section in your response until the very end.

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

    sections.append(output_format)

    context = "\n\n---\n\n".join(sections)
    log.bind(context_len=len(context)).success("Run context built")
    return context
