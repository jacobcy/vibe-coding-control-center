"""Plan context builder - assemble prompt body for planning agent.

Public API:
- ``build_plan_prompt_body(request, config)`` - assemble the full plan prompt string
- ``make_plan_context_builder(request, config)`` - PromptContextBuilder (via assembler)
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from loguru import logger

from vibe3.clients import resolve_runtime_asset
from vibe3.clients.runtime_assets import bundled_project_root
from vibe3.config import VibeConfig, get_resolver
from vibe3.models import PlanRequest, PromptContextMode
from vibe3.prompts import (
    PromptContextBuilder,
    PromptManifest,
    PromptProvider,
    build_tools_guide_section,
    make_context_builder,
    resolve_common_rules_path,
)
from vibe3.prompts.models import MaterialLayer

PlanPromptMode = Literal["first", "retry"]


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


def _build_plan_policy_section(policy_path: str | None) -> str | None:
    """Build plan policy section from file."""
    if not policy_path:
        return None

    log = logger.bind(domain="plan_context_builder", action="build_plan_policy_section")
    path = resolve_runtime_asset(policy_path)
    if not path.exists():
        return None

    try:
        content = path.read_text(encoding="utf-8")
        log.success("Plan policy section built")
        return content
    except OSError as e:
        log.bind(error=str(e), path=str(policy_path)).warning(
            "Could not read plan policy"
        )
        return None


def _build_plan_task_section(
    request: PlanRequest,
    task_text: str | None,
) -> str:
    """Build plan task section."""
    if task_text:
        if request.task_guidance:
            return f"## Planning Task\n{task_text}\n\n{request.task_guidance}"
        return f"## Planning Task\n{task_text}"

    scope_info = ""
    if request.scope.kind == "task" and request.scope.issue_number:
        scope_info = f"\n- Issue: #{request.scope.issue_number}"
    elif request.scope.kind == "spec" and request.scope.description:
        section = f"""## Specification

{request.scope.description}

## Planning Task

- Create a step-by-step implementation plan based on the specification
- Identify dependencies between steps
- Estimate effort for each step
- Flag potential risks or blockers
- Maximum {request.max_steps} steps"""
        if request.task_guidance:
            section += f"\n\n{request.task_guidance}"
        return section

    section = f"""## Planning Task

- Create a step-by-step implementation plan
- Identify dependencies between steps
- Estimate effort for each step
- Flag potential risks or blockers
- Maximum {request.max_steps} steps{scope_info}"""
    if request.task_guidance:
        section += f"\n\n{request.task_guidance}"
    return section


def _build_plan_output_contract_section(output_format: str | None) -> str:
    """Build plan output contract section."""
    if output_format:
        return f"## Output format requirements\n{output_format}"

    return """## Output format requirements

Output a structured plan in this format:

## Plan Summary
[1-2 sentence overview]

## Steps
1. [Step description]
   - Files: [list of files to modify]
   - Effort: [S/M/L]
   - Dependencies: [step numbers or "none"]

2. [Step description]
   - Files: [list of files to modify]
   - Effort: [S/M/L]
   - Dependencies: [step numbers or "none"]

## Risks
- [Risk description]

## Notes
[Optional additional context]"""


def _plan_variant(mode: PlanPromptMode, context_mode: PromptContextMode) -> str:
    if context_mode == "resume":
        return f"{mode}.resume"
    return f"{mode}.bootstrap"


def describe_plan_sections(
    mode: PlanPromptMode,
    context_mode: PromptContextMode,
    prompts_path: Path | None = None,
) -> list[str]:
    """Return configured plan.default section keys for dry-run summaries."""
    variant = _plan_variant(mode, context_mode)
    manifest = PromptManifest.load_for_prompts_path(prompts_path)
    # Get section sources with active_layers for enabled/disabled status marking
    active_layers = _detect_active_layers()
    sources = manifest.get_section_sources("plan.default", variant, active_layers)
    return [s.key for s in sources]


def _build_plan_prompt_providers(
    request: PlanRequest,
    config: VibeConfig,
    context_mode: PromptContextMode,
) -> dict[str, PromptProvider]:
    """Build providers used by config/prompts/prompt-recipes.yaml plan sections."""
    plan_config = getattr(config, "plan", None)
    task_request = (
        request if context_mode == "bootstrap" else PlanRequest(scope=request.scope)
    )
    resolver = get_resolver()

    def plan_policy() -> str | None:
        if not plan_config:
            return None
        policy_path = (
            plan_config.policy_file
            if plan_config.policy_file is not None
            else resolver.get_policy_path("plan")
        )
        if policy_path:
            return _build_plan_policy_section(policy_path)
        return None

    def plan_output_format() -> str:
        output_format = (
            getattr(plan_config, "output_format", None) if plan_config else None
        )
        return _build_plan_output_contract_section(output_format)

    def plan_retry_task() -> str | None:
        return getattr(plan_config, "retry_task", None) if plan_config else None

    def plan_exit_contract() -> str:
        plan_task_text = (
            getattr(plan_config, "plan_task", None) if plan_config else None
        )
        return _build_plan_task_section(task_request, plan_task_text)

    def common_rules_section() -> str | None:
        return build_tools_guide_section(
            resolve_common_rules_path(
                plan_config.common_rules if plan_config else None, resolver
            )
        )

    return {
        "plan.policy": plan_policy,
        "common.rules": common_rules_section,
        "plan.output_format": plan_output_format,
        "plan.retry_task": plan_retry_task,
        "plan.exit_contract": plan_exit_contract,
        # Backward-compatible alias for local recipe overrides.
        "plan.task": plan_exit_contract,
    }


def build_plan_prompt_body(
    request: PlanRequest,
    config: VibeConfig | None = None,
    mode: PlanPromptMode = "first",
    context_mode: PromptContextMode = "bootstrap",
    prompts_path: Path | None = None,
) -> str:
    """Assemble the plan prompt body from policy, tools guide, task, and output format.

    Args:
        request: PlanRequest with scope and task guidance.
        config: VibeConfig instance.
        mode: Prompt mode. ``retry`` revises an existing plan.
        context_mode: ``resume`` means an existing session is available, so use
            the minimal retry prompt instead of re-sending policy/rules context.
        prompts_path: Optional custom path to prompts.yaml. When provided,
            loads the prompt-recipes.yaml from the same directory.

    Returns:
        Assembled plan prompt body string.
    """
    log = logger.bind(
        domain="plan_context_builder",
        action="build_plan_prompt_body",
        prompt_mode=mode,
        context_mode=context_mode,
    )
    log.info("Building plan prompt body")

    if config is None:
        config = VibeConfig.get_defaults()

    if prompts_path is not None:
        manifest = PromptManifest.load(prompts_path.parent / "prompt-recipes.yaml")
    else:
        manifest = PromptManifest.load_default()

    # Detect active layers based on runtime context
    active_layers = _detect_active_layers()

    body = manifest.render_sections(
        recipe_key="plan.default",
        variant_key=_plan_variant(mode, context_mode),
        providers=_build_plan_prompt_providers(request, config, context_mode),
        active_layers=active_layers,
    )
    log.bind(body_len=len(body)).success("Plan prompt body built")
    return body


def make_plan_context_builder(
    request: PlanRequest,
    config: VibeConfig | None = None,
    prompts_path: Path | None = None,
) -> PromptContextBuilder:
    """Create a PromptContextBuilder for the plan command.

    Routes through PromptAssembler with template key ``plan.default``
    and a single provider that calls ``build_plan_prompt_body``.
    """
    cfg = config or VibeConfig.get_defaults()
    return make_context_builder(
        template_key="plan.default",
        body_provider_key="plan.context",
        body_fn=lambda: build_plan_prompt_body(request, cfg, prompts_path=prompts_path),
        prompts_path=prompts_path,
    )
