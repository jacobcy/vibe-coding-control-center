"""Context builder - assemble prompt body for the review agent.

Public API:
- ``build_review_prompt_body(request, config)`` - assemble review prompt body
- ``make_review_context_builder(request, config)`` - PromptContextBuilder

Use ``PromptManifest`` and ``PromptContextBuilder`` for custom prompt assembly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from loguru import logger

from vibe3.analysis import build_snapshot_diff_section
from vibe3.clients import resolve_runtime_asset
from vibe3.clients.runtime_assets import bundled_project_root
from vibe3.config import VibeConfig, get_resolver
from vibe3.models import PromptContextMode, ReviewRequest
from vibe3.prompts import (
    ContextBuilderError,
    PromptContextBuilder,
    PromptManifest,
    PromptProvider,
    build_tools_guide_section,
    make_context_builder,
    resolve_common_rules_path,
)
from vibe3.prompts.models import MaterialLayer

ReviewPromptMode = Literal["first", "retry"]


def _detect_active_layers() -> set[MaterialLayer]:
    """Detect which material layers are active in the current runtime context.

    When running inside the vibe-center repo, all layers are active.
    When running cross-project, only core_invariant and runtime_evidence
    from vibe-center are active; repo_profile and project_policy come
    from the target repo's own config.
    """
    try:
        Path.cwd().resolve().relative_to(bundled_project_root())
        # Same repo: all layers active
        return {
            MaterialLayer.CORE_INVARIANT,
            MaterialLayer.REPO_PROFILE,
            MaterialLayer.PROJECT_POLICY,
            MaterialLayer.RUNTIME_EVIDENCE,
        }
    except ValueError:
        # Cross-project: only core and runtime from vibe-center
        return {MaterialLayer.CORE_INVARIANT, MaterialLayer.RUNTIME_EVIDENCE}


def _build_policy_section(policy_path: str) -> str:
    """Build policy section from file.

    Source: config/v3/settings.yaml (review.policy_file)

    Args:
        policy_path: Path to review policy markdown file

    Returns:
        Policy markdown content

    Raises:
        ContextBuilderError: Cannot read policy file
    """
    log = logger.bind(domain="context_builder", action="build_policy_section")
    try:
        content = resolve_runtime_asset(policy_path).read_text(encoding="utf-8")
        log.success("Policy section built")
        return content
    except OSError as e:
        raise ContextBuilderError(f"Cannot read policy: {e}") from e


def _build_ast_analysis_section(
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


def _build_review_task_section(task_text: str | None) -> str:
    """Build review task section.

    Source: config/prompts/prompts.yaml (review.review_task) via VibeConfig.

    Args:
        task_text: Task text from config (optional)

    Returns:
        Review task section, or empty string if task_text is empty/None
    """
    if task_text:
        return f"## Review Task\n{task_text}"

    logger.warning("build_review_task_section: task_text is empty or None")
    return ""


def _build_output_contract_section(output_format: str | None) -> str:
    """Build output contract section.

    Source: config/prompts/prompts.yaml (review.output_format) via VibeConfig.

    Args:
        output_format: Output format text from config (optional)

    Returns:
        Output format section, or empty string if output_format is empty/None
    """
    if output_format:
        return f"## Output format requirements\n{output_format}"

    logger.warning("_build_output_contract_section: output_format is empty or None")
    return ""


def _review_variant(mode: ReviewPromptMode, context_mode: PromptContextMode) -> str:
    if context_mode == "resume":
        return f"{mode}.resume"
    return f"{mode}.bootstrap"


def describe_review_sections(
    mode: ReviewPromptMode,
    context_mode: PromptContextMode,
    prompts_path: Path | None = None,
) -> list[str]:
    """Return configured review.default section keys for dry-run summaries."""
    variant = _review_variant(mode, context_mode)
    manifest = PromptManifest.load_for_prompts_path(prompts_path)
    # Get section sources with active_layers for enabled/disabled status marking
    active_layers = _detect_active_layers()
    sources = manifest.get_section_sources("review.default", variant, active_layers)
    return [s.key for s in sources]


def _build_review_prompt_providers(
    request: ReviewRequest,
    config: VibeConfig,
) -> dict[str, PromptProvider]:
    """Build providers used by config/prompts/prompt-recipes.yaml review sections."""

    def review_retry_task() -> str | None:
        return getattr(config.review, "retry_task", None)

    def review_exit_contract() -> str:
        return _build_review_task_section(config.review.review_task)

    resolver = get_resolver()

    def review_policy() -> str:
        policy_path = (
            config.review.policy_file
            if config.review.policy_file is not None
            else resolver.get_policy_path("review")
        )
        return _build_policy_section(policy_path) if policy_path else ""

    def common_rules_section() -> str | None:
        return build_tools_guide_section(
            resolve_common_rules_path(config.review.common_rules, resolver)
        )

    return {
        "review.policy": review_policy,
        "common.rules": common_rules_section,
        "review.snapshot_diff": lambda: build_snapshot_diff_section(
            request.structure_diff
        ),
        "review.ast_analysis": lambda: _build_ast_analysis_section(
            request.changed_symbols, request.symbol_dag
        ),
        "review.output_format": lambda: _build_output_contract_section(
            config.review.output_format
        ),
        "review.retry_task": review_retry_task,
        "review.exit_contract": review_exit_contract,
    }


def build_review_prompt_body(
    request: ReviewRequest,
    config: VibeConfig | None = None,
    mode: ReviewPromptMode = "first",
    context_mode: PromptContextMode = "bootstrap",
    prompts_path: Path | None = None,
) -> str:
    """Assemble the review prompt body from policy, tools, analysis, and output format.

    Args:
        request: Review request containing scope, symbols, and task.
        config: VibeConfig instance (loads from default migrated config if None).
        mode: Prompt mode. ``retry`` revisits an existing review round.
        context_mode: ``resume`` means an existing session is available, so use
            the minimal retry prompt instead of re-sending policy/rules context.
        prompts_path: Optional custom path to prompts.yaml. When provided,
            loads the prompt-recipes.yaml from the same directory.

    Returns:
        Assembled review prompt body string.

    Raises:
        ContextBuilderError: Build failed.
    """
    log = logger.bind(
        domain="context_builder",
        action="build_review_prompt_body",
        prompt_mode=mode,
        context_mode=context_mode,
    )
    log.info("Building review prompt body")

    if config is None:
        config = VibeConfig.get_defaults()

    if prompts_path is not None:
        manifest = PromptManifest.load(prompts_path.parent / "prompt-recipes.yaml")
    else:
        manifest = PromptManifest.load_default()

    # Detect active layers based on runtime context
    active_layers = _detect_active_layers()

    body = manifest.render_sections(
        recipe_key="review.default",
        variant_key=_review_variant(mode, context_mode),
        providers=_build_review_prompt_providers(request, config),
        active_layers=active_layers,
    )
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
        body_fn=lambda: build_review_prompt_body(
            request, cfg, prompts_path=prompts_path
        ),
        prompts_path=prompts_path,
    )
