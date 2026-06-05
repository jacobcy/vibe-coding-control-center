"""Governance role definition and request builders."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients import GitHubClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.config.role_gates import GOVERNANCE_GATE_CONFIG
from vibe3.execution.execution_role_policy import ExecutionRolePolicyService
from vibe3.execution.issue_role_support import resolve_orchestra_repo_root
from vibe3.models.execution_request import ExecutionRequest
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.logging import (
    append_governance_event,
    governance_dry_run_dir,
)
from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.manifest import PromptManifest, PromptRecipeDefinition
from vibe3.prompts.models import (
    PromptMaterialSpec,
    PromptRecipe,
    PromptRenderResult,
    PromptVariableSource,
    VariableSourceKind,
)
from vibe3.prompts.provider_registry import ProviderRegistry
from vibe3.prompts.template_loader import DEFAULT_PROMPTS_PATH
from vibe3.roles.definitions import RoleDefinition
from vibe3.roles.governance_utils import (
    build_broader_repo_entries,
    build_code_auditor_context,
    build_issue_context,
    find_material_in_catalog,
    get_governed_issue_numbers,
)
from vibe3.services.orchestra_status_service import OrchestraStatusService

GOVERNANCE_ROLE = RoleDefinition(
    name="governance",
    registry_role="governance",
    worktree=GOVERNANCE_GATE_CONFIG,
)

GOVERNANCE_TASK_PROMPT = (
    "Run orchestra governance scan. "
    "Analyze the current runtime snapshot, follow the governance supervisor "
    "material only, produce governance conclusions or minimal allowed actions, "
    "then stop. Do not switch into execution-plan or implementation mode."
)

# Runtime variable keys that come from the snapshot (resolved as providers).
_GOVERNANCE_RUNTIME_VARS = (
    "issue_scope_name",
    "scope_note",
    "server_status",
    "active_count",
    "active_flows",
    "active_worktrees",
    "running_issue_count",
    "queued_issue_count",
    "suggested_issue_count",
    "circuit_breaker_state",
    "circuit_breaker_failures",
    "issue_list",
    "running_issue_details",
    "suggested_issue_details",
    "truncated_note",
)


def _resolve_governance_material(
    config: OrchestraConfig,
    execution_count: int,
) -> str:
    _ = config
    catalog = load_governance_material_catalog()
    return catalog[execution_count % len(catalog)].name


def _load_governance_recipe_definition() -> PromptRecipeDefinition:
    return PromptManifest.load_default().recipe("governance.scan")


def load_governance_material_catalog() -> tuple[PromptMaterialSpec, ...]:
    """Load the governance material catalog from prompt manifest.

    Returns:
        Tuple of PromptMaterialSpec objects for governance materials.
    """
    recipe_def = _load_governance_recipe_definition()
    if not recipe_def.loaded_definition:
        raise ValueError("governance.scan recipe not properly loaded")
    catalog = recipe_def.loaded_definition.material_catalog
    if not catalog:
        raise ValueError("governance.scan recipe requires material_catalog")
    return catalog


def build_governance_snapshot_context(
    snapshot: Any,
    *,
    config: OrchestraConfig | None = None,
    tick_count: int = 0,
    execution_count: int = 0,
    material_override: str | None = None,
    github: GitHubClient | None = None,
) -> dict[str, Any]:
    """Convert runtime observations into the governance prompt context dict."""
    config = config or load_orchestra_config()
    if material_override:
        catalog = load_governance_material_catalog()
        selected = find_material_in_catalog(catalog, material_override)
        if not selected:
            raise ValueError(
                f"Material '{material_override}' not found in governance catalog"
            )
        current_material = selected.name
    else:
        current_material = _resolve_governance_material(config, execution_count)
    material_name = Path(current_material).name

    if material_name == "roadmap-intake.md":
        broader_entries = build_broader_repo_entries(
            config,
            current_material=current_material,
            github=github,
        )
        return build_issue_context(
            broader_entries,
            server_running=snapshot.server_running,
            active_flows=snapshot.active_flows,
            active_worktrees=snapshot.active_worktrees,
            queued_issues=snapshot.queued_issues,
            circuit_breaker_state=snapshot.circuit_breaker_state,
            circuit_breaker_failures=snapshot.circuit_breaker_failures,
            issue_scope_name="broader repo issue pool",
            scope_note=(
                "以下候选来自 broader repo issue pool；"
                "目标是识别适合自动化纳入 assignee issue pool 的对象。"
            ),
        )

    if material_name == "cron-supervisor.md":
        broader_entries = build_broader_repo_entries(
            config,
            current_material=current_material,
            github=github,
        )
        return build_issue_context(
            broader_entries,
            server_running=snapshot.server_running,
            active_flows=snapshot.active_flows,
            active_worktrees=snapshot.active_worktrees,
            queued_issues=snapshot.queued_issues,
            circuit_breaker_state=snapshot.circuit_breaker_state,
            circuit_breaker_failures=snapshot.circuit_breaker_failures,
            issue_scope_name="broader repo docs scope",
            scope_note=(
                "以下候选来自 broader repo 文档范围；"
                "目标是挑选最多 5 个需要语义对齐的过时文档对象。"
            ),
        )

    if material_name == "code-auditor.md":
        return build_code_auditor_context(snapshot, tick_count=tick_count)

    # Default: assignee-pool path
    github = github or GitHubClient()
    governed_numbers = get_governed_issue_numbers(github, config)

    # Filter out orchestra-governed issues from the active issues
    active_entries = tuple(snapshot.active_issues)
    filtered_entries = tuple(
        entry for entry in active_entries if entry.number not in governed_numbers
    )

    skipped_count = len(active_entries) - len(filtered_entries)
    if skipped_count > 0:
        logger.bind(domain="governance").info(
            f"Filtered {skipped_count} orchestra-governed issues from pool scan"
        )

    return build_issue_context(
        filtered_entries,
        server_running=snapshot.server_running,
        active_flows=snapshot.active_flows,
        active_worktrees=snapshot.active_worktrees,
        queued_issues=snapshot.queued_issues,
        circuit_breaker_state=snapshot.circuit_breaker_state,
        circuit_breaker_failures=snapshot.circuit_breaker_failures,
        issue_scope_name="assignee issue pool",
        scope_note=(
            "以下均为 assignee issue pool 内的建议；"
            "最终仍需结合 flow / worktree / PR 现场判断。"
        ),
    )


def _build_runtime_registry(context: dict[str, Any]) -> ProviderRegistry:
    """Build a provider registry with snapshot values for prompt rendering."""
    registry = ProviderRegistry()

    def create_provider(value: str) -> Callable[[Any], str]:
        return lambda _: value

    for key in _GOVERNANCE_RUNTIME_VARS:
        registry.register(
            f"governance.{key}", create_provider(str(context.get(key, "")))
        )
    return registry


def build_governance_recipe(
    config: OrchestraConfig,
    tick_count: int = 0,
    execution_count: int = 0,
    material_override: str | None = None,
) -> PromptRecipe:
    """Build the PromptRecipe for governance dispatch."""
    recipe_def = _load_governance_recipe_definition()
    if not recipe_def.loaded_definition:
        raise ValueError("governance.scan recipe not properly loaded")
    catalog = recipe_def.loaded_definition.material_catalog
    if not catalog:
        raise ValueError("governance.scan recipe requires material_catalog")

    # Override material if specified, otherwise use tick-based rotation
    if material_override:
        # Find the matching material in catalog using flexible matching
        current = find_material_in_catalog(catalog, material_override)
        if not current:
            # Generate helpful error with available materials
            from vibe3.roles.governance_utils import normalize_material_name

            available = sorted(set(normalize_material_name(m.name) for m in catalog))
            raise ValueError(
                f"Material '{material_override}' not found in catalog.\n"
                f"Available materials: {', '.join(available)}\n"
                f"You can specify materials by short name (e.g., 'roadmap-intake') "
                f"or full path (e.g., 'supervisor/governance/roadmap-intake.md')"
            )
        current_material = current.name
    else:
        # Use execution_count for material rotation (independent of tick_count)
        current = catalog[execution_count % len(catalog)]
        current_material = current.name

    supervisor_content_source = current.source

    manager_usernames = OrchestraStatusService.get_manager_usernames(config)
    manager_bot = manager_usernames[0] if manager_usernames else "vibe-manager-agent"

    variables: dict[str, PromptVariableSource] = {
        "supervisor_name": PromptVariableSource(
            kind=VariableSourceKind.LITERAL, value=current_material
        ),
        "supervisor_content": supervisor_content_source,
        "manager_bot": PromptVariableSource(
            kind=VariableSourceKind.LITERAL, value=manager_bot
        ),
    }
    for key in _GOVERNANCE_RUNTIME_VARS:
        variables[key] = PromptVariableSource(
            kind=VariableSourceKind.PROVIDER, provider=f"governance.{key}"
        )

    template_key = config.governance.prompt_template
    if recipe_def.loaded_definition:
        template_key = recipe_def.loaded_definition.template_key

    return PromptRecipe(
        template_key=template_key,
        variables=variables,
        description="Orchestra governance scan",
    )


def render_governance_prompt(
    config: OrchestraConfig,
    snapshot_context: dict[str, Any],
    prompts_path: Path | None = None,
    tick_count: int = 0,
    execution_count: int = 0,
    material_override: str | None = None,
) -> PromptRenderResult:
    """Render governance plan from snapshot context via PromptAssembler."""
    prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
    recipe = build_governance_recipe(
        config,
        tick_count=tick_count,
        execution_count=execution_count,
        material_override=material_override,
    )
    registry = _build_runtime_registry(snapshot_context)
    assembler = PromptAssembler(prompts_path=prompts_path, registry=registry)
    return assembler.render(recipe, runtime_context=snapshot_context)


def resolve_governance_options(config: OrchestraConfig) -> Any:
    """Resolve governance agent options."""
    return ExecutionRolePolicyService(config).resolve_effective_agent_options(
        "governance"
    )


def build_governance_execution_name(tick_count: int) -> str:
    """Build unique execution name for a governance scan tick."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"vibe3-governance-scan-{timestamp}-t{tick_count}"


def build_governance_request(
    config: OrchestraConfig,
    tick_count: int,
    snapshot: Any,
    repo_path: Path | None = None,
    prompts_path: Path | None = None,
    execution_count: int = 0,
) -> ExecutionRequest | None:
    """Build governance execution request.

    Returns None if circuit breaker is open or dry-run mode is active.
    """
    log = logger.bind(domain="orchestra", action="governance")

    if snapshot.circuit_breaker_state == "open":
        log.warning("Skipping governance: circuit breaker is OPEN")
        root = repo_path or resolve_orchestra_repo_root()
        append_governance_event("skipped: circuit breaker OPEN", repo_root=root)
        return None

    snapshot_context = build_governance_snapshot_context(
        snapshot,
        config=config,
        tick_count=tick_count,
        execution_count=execution_count,
    )
    render_result = render_governance_prompt(
        config,
        snapshot_context,
        prompts_path,
        tick_count=tick_count,
        execution_count=execution_count,
    )
    plan_content = render_result.rendered_text
    current_material = _resolve_governance_material(config, execution_count)

    if config.governance.dry_run:
        root = repo_path or resolve_orchestra_repo_root()
        dry_run_plan_path = _write_dry_run_plan(root, plan_content, current_material)
        log.info("Dry run: governance plan prepared")
        log.info(f"Dry run plan file: {dry_run_plan_path}")
        append_governance_event(
            f"dry-run plan written ({current_material}): {dry_run_plan_path}",
            repo_root=root,
        )
        return None

    options = resolve_governance_options(config)

    root = repo_path or resolve_orchestra_repo_root()
    append_governance_event(
        f"dispatching governance scan tick={tick_count} material={current_material}",
        repo_root=root,
    )

    return ExecutionRequest(
        role="governance",
        target_branch="governance",
        target_id=1,
        execution_name=build_governance_execution_name(tick_count),
        prompt=plan_content,
        options=options,
        refs={"task": GOVERNANCE_TASK_PROMPT},
        actor="orchestra:governance",
        mode="async",
        worktree_requirement=GOVERNANCE_ROLE.worktree,
    )


def _write_dry_run_plan(
    repo_path: Path, plan_content: str, current_material: str | None = None
) -> Path:
    """Write governance dry-run plan to a temp file."""
    output_dir = governance_dry_run_dir(repo_path)
    material_slug = (
        Path(current_material).stem.replace("-", "_") if current_material else "unknown"
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".md",
        prefix=f"governance_dry_run_{material_slug}_",
        dir=output_dir,
        delete=False,
    ) as handle:
        handle.write(plan_content)
        return Path(handle.name)
