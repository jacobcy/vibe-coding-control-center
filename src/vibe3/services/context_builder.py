"""Context builder - Build context for codeagent-wrapper review.

This module constructs a stable prompt format for the review agent.
"""

from pathlib import Path

from loguru import logger

from vibe3.config.settings import VibeConfig
from vibe3.exceptions import VibeError


class ContextBuilderError(VibeError):
    """Context build failed."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Context build failed: {details}", recoverable=False)


def build_review_context(
    policy_path: str | None = None,
    changed_symbols: dict[str, list[str]] | None = None,
    symbol_dag: dict[str, list[str]] | None = None,
    config: VibeConfig | None = None,
) -> str:
    """Build review context with AST-level analysis.

    Reviewer runs git diff themselves to see file-level changes.
    We provide AST-level insights they can't get from diff:
    - Which functions were changed (symbol-level)
    - Who calls these functions (DAG impact)
    - Tools available for deeper analysis

    Args:
        policy_path: path to review-policy.md (reads from config if None)
        changed_symbols: file -> list of changed function names
        symbol_dag: function -> list of caller locations
        config: VibeConfig instance (loads from settings.yaml if None)

    Returns:
        Complete context string

    Raises:
        ContextBuilderError: build failed
    """
    log = logger.bind(domain="context_builder", action="build_review_context")
    log.info("Building review context")

    # Load config if not provided
    if config is None:
        config = VibeConfig.get_defaults()

    # Use policy_path from parameter or config
    actual_policy_path = policy_path or config.review.policy_file

    try:
        policy = Path(actual_policy_path).read_text(encoding="utf-8")
    except OSError as e:
        raise ContextBuilderError(f"Cannot read policy: {e}") from e

    sections: list[str] = [policy]

    # Add tools guide (project-specific analysis tools)
    if config.review.tools_guide_file:
        tools_guide_path = Path(config.review.tools_guide_file)
        if tools_guide_path.exists():
            try:
                tools_guide = tools_guide_path.read_text(encoding="utf-8")
                sections.append(f"## Available Tools\n\n{tools_guide}")
            except OSError as e:
                log.bind(
                    error=str(e), path=str(tools_guide_path)
                ).warning("Could not read tools guide")

    # Add AST-level analysis if available
    if changed_symbols or symbol_dag:
        ast_parts: list[str] = []
        if changed_symbols:
            import json

            symbols_json = json.dumps(changed_symbols, indent=2)
            ast_parts.append(
                f"### Changed Functions (AST Analysis)\n"
                f"```json\n{symbols_json}\n```"
            )
        if symbol_dag:
            import json

            dag_json = json.dumps(symbol_dag, indent=2)
            ast_parts.append(
                f"### Function Call Chain (DAG)\n" f"```json\n{dag_json}\n```"
            )

        ast_section = "## AST Analysis\n" + "\n\n".join(ast_parts)
        sections.append(ast_section)

    # Add review task guidance from config
    review_task_text = config.review.review_task
    if review_task_text:
        review_task = f"## Review Task\n{review_task_text}"
    else:
        # Fallback if not configured
        review_task = """## Review Task
- Run `git diff <base>...HEAD` to see file changes
- Review only changed code, not the entire codebase
- Use AST analysis to understand function-level impact
- Prioritize: correctness, regression risk, API breaks
- Focus on actionable, specific findings"""
    sections.append(review_task)

    # Add output format requirements from config
    output_format_text = config.review.output_format
    if output_format_text:
        output_format_section = f"## Output format requirements\n{output_format_text}"
    else:
        # Fallback if not configured
        output_format_section = """## Output format requirements

Each finding should follow this format:
path/to/file.py:42 [MAJOR] concise issue description

The final line must be:
VERDICT: PASS | MAJOR | BLOCK

Where:
- PASS: No significant issues found
- MAJOR: Issues found that should be addressed before merge
- BLOCK: Critical issues that must be fixed before merge"""
    sections.append(output_format_section)

    context = "\n\n---\n\n".join(sections)
    log.bind(context_len=len(context)).success("Review context built")
    return context


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
