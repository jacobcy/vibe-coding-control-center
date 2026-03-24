"""Context builder - Build context for codeagent-wrapper review.

This module constructs a stable prompt format for the review agent through
composable section builders. Each section builder is responsible for one
aspect of the review context:

- build_policy_section: Static review policy
- build_tools_guide_section: Project-specific analysis tools
- build_ast_analysis_section: Runtime symbol/DAG analysis
- build_review_task_section: Task guidance
- build_output_contract_section: Output format requirements

The main build_review_context() function orchestrates these sections.
"""

import json
from pathlib import Path

from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.exceptions import VibeError
from vibe3.models.review import ReviewRequest
from vibe3.services.snapshot_diff_section import build_snapshot_diff_section


class ContextBuilderError(VibeError):
    """Context build failed."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Context build failed: {details}", recoverable=False)


def build_policy_section(policy_path: str) -> str:
    """Build policy section from file.

    Source: config/settings.yaml (review.policy_file)

    Args:
        policy_path: Path to review policy markdown file

    Returns:
        Policy markdown content

    Raises:
        ContextBuilderError: Cannot read policy file
    """
    log = logger.bind(domain="context_builder", action="build_policy_section")
    try:
        content = Path(policy_path).read_text(encoding="utf-8")
        log.success("Policy section built")
        return content
    except OSError as e:
        raise ContextBuilderError(f"Cannot read policy: {e}") from e


def build_tools_guide_section(tools_guide_path: str | None) -> str | None:
    """Build tools guide section from file.

    Source: config/settings.yaml (review.common_rules)

    Args:
        tools_guide_path: Path to tools guide file (optional)

    Returns:
        Tools guide section or None if not configured/available
    """
    if not tools_guide_path:
        return None

    log = logger.bind(domain="context_builder", action="build_tools_guide_section")
    path = Path(tools_guide_path)
    if not path.exists():
        return None

    try:
        tools_guide = path.read_text(encoding="utf-8")
        log.success("Tools guide section built")
        return f"## Available Tools\n\n{tools_guide}"
    except OSError as e:
        log.bind(error=str(e), path=str(tools_guide_path)).warning(
            "Could not read tools guide"
        )
        return None


def build_ast_analysis_section(
    changed_symbols: dict[str, list[str]] | None,
    symbol_dag: dict[str, list[str]] | None,
) -> str | None:
    """Build AST analysis section from runtime data.

    Source: Runtime (inspect command output)

    Args:
        changed_symbols: Map of file -> list of changed function names
        symbol_dag: Map of function -> list of caller locations

    Returns:
        AST analysis section or None if no data provided
    """
    if not changed_symbols and not symbol_dag:
        return None

    ast_parts: list[str] = []

    if changed_symbols:
        symbols_json = json.dumps(changed_symbols, indent=2)
        ast_parts.append(
            f"### Changed Functions (AST Analysis)\n```json\n{symbols_json}\n```"
        )

    if symbol_dag:
        dag_json = json.dumps(symbol_dag, indent=2)
        ast_parts.append(f"### Function Call Chain (DAG)\n```json\n{dag_json}\n```")

    return "## AST Analysis\n" + "\n\n".join(ast_parts)


def build_review_task_section(task_text: str | None) -> str:
    """Build review task section.

    Source: config/settings.yaml (review.review_task) or default

    Args:
        task_text: Task text from config (optional)

    Returns:
        Review task section
    """
    if task_text:
        return f"## Review Task\n{task_text}"

    # Default task guidance
    return """## Review Task
- Run `git diff <base>...HEAD` to see file changes
- Review only changed code, not the entire codebase
- Use AST analysis to understand function-level impact
- Prioritize: correctness, regression risk, API breaks
- Focus on actionable, specific findings"""


def build_output_contract_section(output_format: str | None) -> str:
    """Build output contract section.

    Source: config/settings.yaml (review.output_format) or default

    Args:
        output_format: Output format text from config (optional)

    Returns:
        Output format section
    """
    if output_format:
        return f"## Output format requirements\n{output_format}"

    # Default output format
    return """## Output format requirements

Each finding should follow this format:
path/to/file.py:42 [MAJOR] concise issue description

The final line must be:
VERDICT: PASS | MAJOR | BLOCK

Where:
- PASS: No significant issues found
- MAJOR: Issues found that should be addressed before merge
- BLOCK: Critical issues that must be fixed before merge"""


def build_review_context(
    request: ReviewRequest, config: VibeConfig | None = None
) -> str:
    """Build review context from request and configuration.

    This is the orchestration function that:
    1. Loads configuration if not provided
    2. Calls section builders
    3. Assembles final prompt

    Args:
        request: Review request containing scope, symbols, and task
        config: VibeConfig instance (loads from settings.yaml if None)

    Returns:
        Complete review context string

    Raises:
        ContextBuilderError: Build failed

    Examples:
        >>> scope = ReviewScope.for_base("main")
        >>> request = ReviewRequest(scope=scope)
        >>> context = build_review_context(request)
        >>> assert "Review Task" in context
        >>> assert "VERDICT" in context
    """
    log = logger.bind(domain="context_builder", action="build_review_context")
    log.info("Building review context")

    # Load config if not provided
    if config is None:
        config = VibeConfig.get_defaults()

    # Build sections
    sections: list[str] = []

    # 1. Policy section (required)
    policy = build_policy_section(config.review.policy_file)
    sections.append(policy)

    # 2. Tools guide section (optional)
    tools_guide = build_tools_guide_section(config.review.common_rules)
    if tools_guide:
        sections.append(tools_guide)

    # 3. Snapshot diff section (optional)
    snapshot_diff = build_snapshot_diff_section(request.structure_diff)
    if snapshot_diff:
        sections.append(snapshot_diff)

    # 4. AST analysis section (optional - always include when available)
    ast_analysis = build_ast_analysis_section(
        request.changed_symbols, request.symbol_dag
    )
    if ast_analysis:
        sections.append(ast_analysis)

    # 4. Review task section
    task = build_review_task_section(request.task_guidance or config.review.review_task)
    sections.append(task)

    # 5. Output contract section
    output_contract = build_output_contract_section(config.review.output_format)
    sections.append(output_contract)

    # Assemble final context
    context = "\n\n---\n\n".join(sections)
    log.bind(context_len=len(context)).success("Review context built")
    return context


# Keep for backward compatibility (if used elsewhere)
def get_git_diff(base: str = "main", head: str = "HEAD") -> str:
    """Get git diff output.

    Args:
        base: base branch or commit
        head: target branch or commit

    Returns:
        diff text

    Raises:
        ContextBuilderError: git command failed
    """
    import subprocess

    log = logger.bind(
        domain="context_builder", action="get_git_diff", base=base, head=head
    )
    log.info("Getting git diff")

    try:
        result = subprocess.run(
            ["git", "diff", "--unified=3", f"{base}...{head}"],
            capture_output=True,
            text=True,
            check=True,
        )
        log.bind(diff_len=len(result.stdout)).success("Got git diff")
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise ContextBuilderError(f"git diff failed: {e.stderr}") from e
