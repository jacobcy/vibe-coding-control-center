"""Context builder - Build context for codeagent-wrapper review.

This module constructs a stable prompt format for the review agent.
"""

from pathlib import Path

from loguru import logger

from vibe3.exceptions import VibeError


class ContextBuilderError(VibeError):
    """Context build failed."""

    def __init__(self, details: str) -> None:
        super().__init__(f"Context build failed: {details}", recoverable=False)


# Output format requirements - stable contract for review agent
OUTPUT_FORMAT_SECTION = """## Output format requirements

Each finding should follow this format:
path/to/file.py:42 [MAJOR] concise issue description

The final line must be:
VERDICT: PASS | MAJOR | BLOCK

Where:
- PASS: No significant issues found
- MAJOR: Issues found that should be addressed before merge
- BLOCK: Critical issues that must be fixed before merge"""


def build_review_context(
    diff: str,
    policy_path: str = ".codex/review-policy.md",
    structure: str | None = None,
    impact: str | None = None,
    dag: str | None = None,
    score: str | None = None,
) -> str:
    """Build complete context for codeagent-wrapper review.

    Args:
        diff: git diff output
        policy_path: path to review-policy.md
        structure: repository structure summary (JSON string)
        impact: symbol analysis result (JSON string)
        dag: impact DAG (JSON string)
        score: risk score (JSON string)

    Returns:
        Complete context string

    Raises:
        ContextBuilderError: build failed
    """
    log = logger.bind(domain="context_builder", action="build_review_context")
    log.info("Building review context")

    try:
        policy = Path(policy_path).read_text(encoding="utf-8")
    except OSError as e:
        raise ContextBuilderError(f"Cannot read policy: {e}") from e

    sections: list[str] = [policy]

    # Build Inspect Summary if any inspect data is provided
    if impact or dag or score:
        inspect_parts: list[str] = []
        if score:
            inspect_parts.append(f"### Risk Score\n```json\n{score}\n```")
        if impact:
            inspect_parts.append(f"### Impact Analysis\n```json\n{impact}\n```")
        if dag:
            inspect_parts.append(f"### Impact DAG\n```json\n{dag}\n```")

        inspect_summary = "## Inspect Summary\n" + "\n\n".join(inspect_parts)
        sections.append(inspect_summary)

    # Add review task guidance
    review_task = """## Review Task
- Review only changed code, not the entire codebase
- Prioritize: correctness, regression risk, config drift, deleted-file risk
- Use inspect score as triage priority, not as sole decision factor
- Focus on actionable, specific findings"""
    sections.append(review_task)

    # Add Git Diff
    sections.append(f"## Git Diff\n```diff\n{diff}\n```")

    # Add output format requirements
    sections.append(OUTPUT_FORMAT_SECTION)

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
