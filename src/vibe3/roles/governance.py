"""Governance role definition and request builders."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients.github_client import GitHubClient
from vibe3.config.orchestra_settings import load_orchestra_config
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.execution_role_policy import ExecutionRolePolicyService
from vibe3.execution.issue_role_support import resolve_orchestra_repo_root
from vibe3.execution.role_contracts import GOVERNANCE_GATE_CONFIG
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
from vibe3.services.label_utils import normalize_assignees, normalize_labels
from vibe3.services.orchestra_status_service import (
    IssueStatusEntry,
    format_issue_runtime_line,
    format_issue_summary_line,
    is_running_issue,
)

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


def _build_issue_context(
    active_entries: tuple[Any, ...],
    *,
    server_running: bool,
    active_flows: int,
    active_worktrees: int,
    queued_issues: tuple[int, ...],
    circuit_breaker_state: str,
    circuit_breaker_failures: int,
    issue_scope_name: str,
    scope_note: str,
) -> dict[str, Any]:
    active_count = len(active_entries)
    running_entries = tuple(
        entry for entry in active_entries if is_running_issue(entry)
    )
    suggested_entries = tuple(
        entry for entry in active_entries if not is_running_issue(entry)
    )
    issue_list = (
        "\n".join(format_issue_summary_line(entry) for entry in active_entries[:20])
        or "(无活跃 issue)"
    )
    running_issue_details = (
        "\n".join(format_issue_runtime_line(entry) for entry in running_entries[:20])
        or "(无 running issues)"
    )
    suggested_issue_details = (
        "\n".join(format_issue_runtime_line(entry) for entry in suggested_entries[:20])
        or "(无建议 issue)"
    )
    truncated_note = (
        f"\n(已截断，仅显示前 20 条 / 共 {active_count} 条活跃 issue)"
        if active_count > 20
        else ""
    )
    return {
        "issue_scope_name": issue_scope_name,
        "scope_note": scope_note,
        "server_status": "running" if server_running else "stopped",
        "active_count": active_count,
        "active_flows": active_flows,
        "active_worktrees": active_worktrees,
        "running_issue_count": len(running_entries),
        "queued_issue_count": len(queued_issues),
        "suggested_issue_count": len(suggested_entries),
        "circuit_breaker_state": circuit_breaker_state,
        "circuit_breaker_failures": circuit_breaker_failures,
        "issue_list": issue_list,
        "running_issue_details": running_issue_details,
        "suggested_issue_details": suggested_issue_details,
        "truncated_note": truncated_note,
    }


def _resolve_governance_material(
    config: OrchestraConfig,
    tick_count: int,
) -> str:
    _ = config
    catalog = _load_governance_material_catalog()
    return catalog[tick_count % len(catalog)].name


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


# Backward compatibility alias
_load_governance_material_catalog = load_governance_material_catalog


def _is_doc_candidate(title: str, body: str, labels: list[str]) -> bool:
    if any(label in {"type/docs", "scope/documentation"} for label in labels):
        return True
    normalized_title = title.lower()
    keywords = ("doc", "docs", "documentation", "readme", "文档", "说明")
    return any(keyword in normalized_title for keyword in keywords)


def _build_broader_repo_entries(
    config: OrchestraConfig,
    *,
    current_material: str,
    github: GitHubClient | None = None,
) -> tuple[Any, ...]:
    github = github or GitHubClient()
    raw_issues = github.list_issues(
        limit=100,
        state="open",
        assignee=None,
        repo=config.repo,
    )
    material_name = Path(current_material).name
    entries: list[Any] = []
    for item in raw_issues:
        number = item.get("number")
        title = item.get("title")
        if not isinstance(number, int) or not isinstance(title, str):
            continue

        labels = normalize_labels(item.get("labels"))
        if "supervisor" in labels or "vibe-task" in labels:
            continue

        assignees = normalize_assignees(item.get("assignees"))
        is_assignee_issue = any(
            assignee in config.get_manager_usernames() for assignee in assignees
        )

        if material_name == "roadmap-intake.md" and is_assignee_issue:
            continue

        body = str(item.get("body") or "")
        if material_name == "cron-supervisor.md":
            if is_assignee_issue or not _is_doc_candidate(title, body, labels):
                continue

        issue = IssueStatusEntry(
            number=number,
            title=title,
            state=None,
            assignee=assignees[0] if assignees else None,
            has_flow=False,
            flow_branch=None,
            has_worktree=False,
            worktree_path=None,
            has_pr=False,
            pr_number=None,
            blocked_by=(),
        )
        entries.append(issue)
    return tuple(entries)


def _get_vibe_task_issue_numbers(
    github: GitHubClient, config: OrchestraConfig
) -> set[int]:
    """Fetch issue numbers that have the vibe-task label.

    Args:
        github: GitHubClient instance for API calls
        config: OrchestraConfig with repo information

    Returns:
        Set of issue numbers that have vibe-task label
    """
    vibe_task_issues = github.list_issues(
        label="vibe-task",
        state="all",
        repo=config.repo,
        limit=5000,  # Fetch all vibe-task issues to avoid truncation
    )
    numbers: set[int] = set()
    for item in vibe_task_issues:
        number = item.get("number")
        if isinstance(number, int):
            numbers.add(number)
    return numbers


def build_governance_snapshot_context(
    snapshot: Any,
    *,
    config: OrchestraConfig | None = None,
    tick_count: int = 0,
    material_override: str | None = None,
    github: GitHubClient | None = None,
) -> dict[str, Any]:
    """Convert runtime observations into the governance prompt context dict."""
    config = config or load_orchestra_config()
    if material_override:
        catalog = load_governance_material_catalog()
        selected = _find_material_in_catalog(catalog, material_override)
        if not selected:
            raise ValueError(
                f"Material '{material_override}' not found in governance catalog"
            )
        current_material = selected.name
    else:
        current_material = _resolve_governance_material(config, tick_count)
    material_name = Path(current_material).name

    if material_name == "roadmap-intake.md":
        broader_entries = _build_broader_repo_entries(
            config,
            current_material=current_material,
            github=github,
        )
        return _build_issue_context(
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
        broader_entries = _build_broader_repo_entries(
            config,
            current_material=current_material,
            github=github,
        )
        return _build_issue_context(
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

    # Default: assignee-pool path
    github = github or GitHubClient()
    vibe_task_numbers = _get_vibe_task_issue_numbers(github, config)

    # Filter out vibe-task labeled issues from the active issues
    active_entries = tuple(snapshot.active_issues)
    filtered_entries = tuple(
        entry for entry in active_entries if entry.number not in vibe_task_numbers
    )

    skipped_count = len(active_entries) - len(filtered_entries)
    if skipped_count > 0:
        logger.bind(domain="governance").info(
            f"Filtered {skipped_count} vibe-task labeled issues from governance scan"
        )

    return _build_issue_context(
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


def _normalize_material_name(material_name: str) -> str:
    """Normalize material name to canonical form for comparison.

    Converts various input formats to canonical form:
    - "roadmap-intake" → "roadmap-intake"
    - "roadmap-intake.md" → "roadmap-intake"
    - "supervisor/governance/roadmap-intake" → "roadmap-intake"
    - "supervisor/governance/roadmap-intake.md" → "roadmap-intake"
    """
    path = Path(material_name)
    # Get the filename without directory
    stem = path.stem if path.suffix == ".md" else path.name
    # If stem still has .md suffix, remove it
    if stem.endswith(".md"):
        stem = stem[:-3]
    return stem


def _find_material_in_catalog(
    catalog: tuple[PromptMaterialSpec, ...], material_override: str
) -> PromptMaterialSpec | None:
    """Find material in catalog using flexible matching.

    Attempts multiple matching strategies:
    1. Exact name match (for advanced users who provide full path)
    2. Normalized match (handles partial names, missing suffixes, etc.)
    """
    # Strategy 1: Exact match
    for material in catalog:
        if material.name == material_override:
            return material

    # Strategy 2: Normalized match
    normalized_target = _normalize_material_name(material_override)
    for material in catalog:
        normalized_catalog_name = _normalize_material_name(material.name)
        if normalized_catalog_name == normalized_target:
            return material

    return None


def build_governance_recipe(
    config: OrchestraConfig, tick_count: int = 0, material_override: str | None = None
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
        current = _find_material_in_catalog(catalog, material_override)
        if not current:
            # Generate helpful error with available materials
            available = sorted(set(_normalize_material_name(m.name) for m in catalog))
            raise ValueError(
                f"Material '{material_override}' not found in catalog.\n"
                f"Available materials: {', '.join(available)}\n"
                f"You can specify materials by short name (e.g., 'roadmap-intake') "
                f"or full path (e.g., 'supervisor/governance/roadmap-intake.md')"
            )
        current_material = current.name
    else:
        # Normal tick-based rotation
        current = catalog[tick_count % len(catalog)]
        current_material = current.name

    supervisor_content_source = current.source

    manager_usernames = config.get_manager_usernames()
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
    material_override: str | None = None,
) -> PromptRenderResult:
    """Render governance plan from snapshot context via PromptAssembler."""
    prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
    recipe = build_governance_recipe(
        config, tick_count=tick_count, material_override=material_override
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
    )
    render_result = render_governance_prompt(
        config, snapshot_context, prompts_path, tick_count=tick_count
    )
    plan_content = render_result.rendered_text
    current_material = _resolve_governance_material(config, tick_count)

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


def build_default_governance_fns() -> Any:
    """Build default GovernanceFunctions implementation.

    Returns an object that implements the GovernanceFunctions protocol
    by wrapping the concrete governance role functions.
    """

    class _DefaultGovernanceFns:
        """Default implementation wrapping governance role functions."""

        def build_snapshot_context(
            self,
            snapshot: Any,
            *,
            config: Any = None,
            tick_count: int = 0,
            material_override: str | None = None,
            **kwargs: Any,
        ) -> dict[str, Any]:
            return build_governance_snapshot_context(
                snapshot,
                config=config,
                tick_count=tick_count,
                material_override=material_override,
                **kwargs,
            )

        def render_prompt(
            self,
            config: Any,
            snapshot_context: dict[str, Any],
            *,
            tick_count: int = 0,
            material_override: str | None = None,
            **kwargs: Any,
        ) -> Any:
            return render_governance_prompt(
                config,
                snapshot_context,
                tick_count=tick_count,
                material_override=material_override,
                **kwargs,
            )

        def resolve_options(self, config: Any) -> Any:
            return resolve_governance_options(config)

        def build_execution_name(self, tick_count: int) -> str:
            return build_governance_execution_name(tick_count)

    return _DefaultGovernanceFns()
