"""Context builder - assemble prompt body for the review agent.

Public API:
- ``build_review_prompt_body(request, config)`` - assemble review prompt body
- ``make_review_context_builder(request, config)`` - PromptContextBuilder

Section builders remain available for direct composition:
- build_policy_section, build_tools_guide_section, build_ast_analysis_section
- build_review_task_section, build_output_contract_section
"""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from vibe3.analysis.snapshot_diff_section import build_snapshot_diff_section
from vibe3.config.settings import VibeConfig
from vibe3.exceptions import VibeError
from vibe3.models.review import ReviewRequest
from vibe3.prompts.context_builder import PromptContextBuilder, make_context_builder


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


def build_review_prompt_body(
    request: ReviewRequest, config: VibeConfig | None = None
) -> str:
    """Assemble the review prompt body from policy, tools, analysis, and output format.

    Args:
        request: Review request containing scope, symbols, and task.
        config: VibeConfig instance (loads from settings.yaml if None).

    Returns:
        Assembled review prompt body string.

    Raises:
        ContextBuilderError: Build failed.
    """
    log = logger.bind(domain="context_builder", action="build_review_prompt_body")
    log.info("Building review prompt body")

    if config is None:
        config = VibeConfig.get_defaults()

    sections: list[str] = []

    policy = build_policy_section(config.review.policy_file)
    sections.append(policy)

    tools_guide = build_tools_guide_section(config.review.common_rules)
    if tools_guide:
        sections.append(tools_guide)

    snapshot_diff = build_snapshot_diff_section(request.structure_diff)
    if snapshot_diff:
        sections.append(snapshot_diff)

    ast_analysis = build_ast_analysis_section(
        request.changed_symbols, request.symbol_dag
    )
    if ast_analysis:
        sections.append(ast_analysis)

    task = build_review_task_section(request.task_guidance or config.review.review_task)
    sections.append(task)

    output_contract = build_output_contract_section(config.review.output_format)
    sections.append(output_contract)

    body = "\n\n---\n\n".join(sections)
    log.bind(body_len=len(body)).success("Review prompt body built")
    return body


def make_review_context_builder(
    request: ReviewRequest,
    config: VibeConfig | None = None,
    prompts_path: Path | None = None,
) -> PromptContextBuilder:
    """Create a PromptContextBuilder for the review command.

    Routes through PromptAssembler with template key ``review.default``
    and a single provider that calls ``build_review_prompt_body``.
    """
    cfg = config or VibeConfig.get_defaults()
    return make_context_builder(
        template_key="review.default",
        body_provider_key="review.context",
        body_fn=lambda: build_review_prompt_body(request, cfg),
        prompts_path=prompts_path,
    )
