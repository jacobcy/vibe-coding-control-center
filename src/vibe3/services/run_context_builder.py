"""Run context builder - Build context for execution agent.

Reuses plan_context_builder logic but changes:
- Task section: execute the plan
- Output contract: code changes + report
"""

from pathlib import Path

from loguru import logger

from vibe3.config.settings import VibeConfig


def build_run_context(
    plan_file: str,
    config: VibeConfig | None = None,
) -> str:
    """Build run context from a plan file.

    Args:
        plan_file: Path to plan file (markdown)
        config: VibeConfig instance

    Returns:
        Complete run context string
    """
    if config is None:
        config = VibeConfig.get_defaults()

    log = logger.bind(domain="run_context_builder", action="build_run_context")
    log.info("Building run context from plan file")

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

    sections.append(f"## Implementation Plan\n\n{plan_content}")

    sections.append("""## Execution Task

- Execute the implementation plan
- Make the necessary code changes
- Ensure changes compile and pass tests
- Output a report of changes made
""")

    sections.append("""## Output format requirements

Output a structured report in this format:

## Changes Made
[List of files changed with brief description of modifications]

## Summary
[1-2 sentence summary of what was accomplished]

## Verification
- [ ] Code compiles
- [ ] Tests pass
- [ ] No regressions
""")

    context = "\n\n---\n\n".join(sections)
    log.bind(context_len=len(context)).success("Run context built")
    return context
