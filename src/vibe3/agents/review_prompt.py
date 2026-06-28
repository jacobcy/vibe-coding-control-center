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

from vibe3.config import VibeConfig, get_resolver
from vibe3.models import PromptContextMode, ReviewRequest
from vibe3.prompts import (
    PromptContextBuilder,
    PromptManifest,
    PromptProvider,
    build_common_rules_section,
    build_policy_section,
    build_project_common_rules_section,
    build_project_policy_section,
    make_context_builder,
)

ReviewPromptMode = Literal["first", "retry"]


def _build_review_observation_section(request: ReviewRequest) -> str | None:
    """Build a review evidence section from the shared observation model."""
    if request.observation is None:
        return None
    payload = request.observation.model_dump(mode="json")
    return (
        "## Review Observation (validated evidence)\n"
        "This data reports Git facts and repository-owned review policy. "
        "Runtime impact analysis is disabled.\n"
        f"```json\n{json.dumps(payload, indent=2)}\n```"
    )


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
    return list(manifest.recipe("review.default").variant(variant).sections)


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

    def review_policy() -> str | None:
        policy_path = (
            config.review.policy_file
            if config.review.policy_file is not None
            else resolver.get_policy_path("review")
        )
        return build_policy_section(policy_path)

    def project_review_policy() -> str | None:
        return build_project_policy_section("review")

    def common_rules_section() -> str | None:
        return build_common_rules_section(config.review.common_rules, resolver)

    def project_common_rules_section() -> str | None:
        return build_project_common_rules_section()

    return {
        "review.policy": review_policy,
        "review.policy@project": project_review_policy,
        "common.rules": common_rules_section,
        "common.rules@project": project_common_rules_section,
        "review.observation": lambda: _build_review_observation_section(request),
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
    annotate_sections: bool = False,
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
        annotate_sections: When True, wrap each section with markers.

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
    body = manifest.render_sections(
        recipe_key="review.default",
        variant_key=_review_variant(mode, context_mode),
        providers=_build_review_prompt_providers(request, config),
        annotate_sections=annotate_sections,
    )
    log.bind(body_len=len(body)).success("Review prompt body built")
    return body


def make_review_context_builder(
    request: ReviewRequest,
    config: VibeConfig | None = None,
    prompts_path: Path | None = None,
    annotate_sections: bool = False,
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
            request,
            cfg,
            prompts_path=prompts_path,
            annotate_sections=annotate_sections,
        ),
        prompts_path=prompts_path,
    )
