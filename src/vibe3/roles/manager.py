"""Manager role definition and request builder."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from loguru import logger

# public-api: pending upstream export
from vibe3.clients import runtime_assets_root

# public-api: pending upstream export
from vibe3.config import (
    MANAGER_GATE_CONFIG,
    diagnose_profile,
    get_convention,
    get_resolver,
)
from vibe3.environment import SessionRegistryService, get_manager_session_name

# public-api: pending upstream export
from vibe3.exceptions import (
    CapacityDeferredError,
    DiagnosticContext,
    MissingResourceError,
    is_transient_git_error,
)
from vibe3.execution import (
    ExecutionRolePolicyService,
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
    build_task_flow_branch_resolver,
    resolve_orchestra_repo_root,
)
from vibe3.models import ExecutionRequest, IssueInfo, IssueState, OrchestraConfig
from vibe3.observability import write_prompt_provenance
from vibe3.prompts import (
    PromptManifest,
    PromptProvider,
    ProviderRegistry,
    collect_dry_run_provenance,
    load_prompt_templates,
    resolve_source,
)
from vibe3.roles.definitions import (
    IssueRoleSyncSpec,
    RoleOutputContract,
    TriggerableRoleDefinition,
)
from vibe3.services.flow import create_flow_manager
from vibe3.services.issue import fail_manager_issue

MANAGER_ROLE = TriggerableRoleDefinition(
    name="manager",
    registry_role="manager",
    worktree=MANAGER_GATE_CONFIG,
    trigger_name="manager",
    trigger_state=IssueState.READY,
    output_contract=RoleOutputContract(),
)

HANDOFF_MANAGER_ROLE = TriggerableRoleDefinition(
    name="manager-handoff",
    registry_role="manager",
    worktree=MANAGER_GATE_CONFIG,
    trigger_name="manager",
    trigger_state=IssueState.HANDOFF,
    output_contract=RoleOutputContract(),
)


def resolve_manager_options(
    config: OrchestraConfig,
    cli_overrides: dict[str, str] | None = None,
) -> Any:
    """Resolve manager agent options.

    Backend/model override uses unified env vars:
    - VIBE_BACKEND_MANAGER
    - VIBE_MODEL_MANAGER

    These are handled by env_override.py and applied to config.
    This function falls back to config resolution if no override.
    """
    _ = cli_overrides
    # Backend/model override handled by env_override.py
    # No need to check env vars here

    # Validate assignee_dispatch configuration
    ad = config.assignee_dispatch
    if not ad.agent and not ad.backend:
        raise MissingResourceError(
            resource="orchestra.assignee_dispatch (agent or backend)",
            context=DiagnosticContext(
                resource_type="orchestra-config",
                search_paths=[
                    str(Path("config/v3/settings.yaml")),
                    str(runtime_assets_root() / "config/v3/settings.yaml"),
                ],
                profile=diagnose_profile(),
                remediation=(
                    "Configure assignee_dispatch.agent or "
                    "assignee_dispatch.backend in config/v3/settings.yaml"
                ),
                ref_issue=1925,
            ),
        )

    return ExecutionRolePolicyService(config).resolve_effective_agent_options("manager")


MANAGER_BRANCH_RESOLVER = build_task_flow_branch_resolver(
    fallback_branch=lambda issue_number, _current_branch: (
        get_convention().branch.canonical_branch(issue_number)
    )
)


def resolve_manager_token(config: OrchestraConfig) -> str | None:
    """Resolve manager token from environment variable.

    Relies on load_keys_env_fallback() (called during config loading)
    to populate os.environ from keys.env if the shell wrapper didn't.
    """
    token_env = config.assignee_dispatch.token_env
    if not token_env:
        return None
    return os.getenv(token_env) or None


def _make_section_provider(
    manager_sections: dict[str, Any], section_key: str
) -> PromptProvider:
    """Create a provider that returns a section from loaded prompts data."""

    def _provider() -> str | None:
        # Extract section name (e.g., "manager.target" -> "target")
        section_name = (
            section_key.split(".", 1)[1] if "." in section_key else section_key
        )
        content = manager_sections.get(section_name, "")
        return str(content) if isinstance(content, str) else None

    return _provider


def build_manager_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    *,
    branch: str | None = None,
    registry: SessionRegistryService | None = None,
    repo_path: Path | None = None,
    actor: str = "orchestra:manager",
    tick_id: int = 0,
) -> ExecutionRequest | None:
    """Build the manager execution request from declarative role policy."""
    flow_manager = create_flow_manager(config, registry=registry)
    try:
        flow = flow_manager.create_flow_for_issue(issue)
    except CapacityDeferredError:
        # Re-raise capacity defer so handler can defer properly
        raise
    except Exception as exc:
        error_msg = str(exc)
        bound_logger = logger.bind(
            domain="manager",
            issue_number=issue.number,
        )
        if is_transient_git_error(error_msg):
            bound_logger.warning(f"create_flow_for_issue failed (transient): {exc}")
        else:
            bound_logger.exception(f"create_flow_for_issue failed: {exc}")

        # Record to error_log table (with guard to avoid masking original error)
        try:
            from vibe3.services.orchestra import record_error

            record_error(
                error_code="E_DISPATCH_FAILURE",
                error_message=f"build_manager_request failed: {exc}",
                severity=None,  # inferred from E_DISPATCH_FAILURE registry entry
                tick_id=tick_id,
                issue_number=issue.number,
            )
        except Exception as record_error_exc:
            logger.bind(
                domain="manager",
                issue_number=issue.number,
            ).warning(f"Failed to record error to error_log: {record_error_exc}")

        # Return None to maintain contract with caller
        # Caller handles None via _block_for_noop()
        return None

    if not flow:
        return None

    flow_branch = branch or str(flow.get("branch") or "").strip()
    if not flow_branch:
        return None

    refs = {"issue_title": issue.title}
    env = dict(os.environ)

    # Inject manager-specific token if configured (Phase 4)
    manager_token = resolve_manager_token(config)
    if manager_token:
        env["GH_TOKEN"] = manager_token
        logger.bind(domain="manager", issue_number=issue.number).info(
            f"Using manager-specific token from {config.assignee_dispatch.token_env}"
        )
    elif config.assignee_dispatch.token_env:
        # Token configured but not available anywhere
        logger.bind(domain="manager", issue_number=issue.number).warning(
            f"Manager token {config.assignee_dispatch.token_env} not set "
            "in env or keys.env. Falling back to user identity (GH_TOKEN). "
            "Isolation is degraded."
        )

    # Backend/model override handled by env_override.py at config load time
    # No need to inject VIBE_BACKEND_MANAGER here

    # Check async_execution config to determine dispatch mode
    if not config.async_execution:
        # Sync mode: blocking execution for debugging
        logger.bind(domain="manager", issue_number=issue.number).info(
            "Using synchronous execution mode (async_execution=False)"
        )
        options = resolve_manager_options(config)
        request = build_manager_sync_request(
            config=config,
            issue=issue,
            branch=flow_branch,
            flow_state=None,
            session_id=None,
            options=options,
            actor=actor,
            dry_run=False,
            show_prompt=False,
            tick_id=tick_id,
        )
        if request.env is None:
            request.env = env
        else:
            request.env.update(env)
        return request

    # Async mode: non-blocking tmux execution (default)
    request = build_issue_async_cli_request(
        role="manager",
        issue=issue,
        target_branch=flow_branch,
        command_args=[
            "internal",
            "manager",
            str(issue.number),
            "--no-async",
        ],
        actor=actor,
        execution_name=get_manager_session_name(issue.number),
        refs=refs,
        worktree_requirement=MANAGER_ROLE.worktree,
        repo_path=repo_path,
        tick_id=tick_id,
    )
    if request.env is None:
        request.env = env
    else:
        request.env.update(env)
    return request


def _record_missing_manager_sections(sections: dict[str, Any]) -> None:
    """Record warning if manager sections are missing from prompts.yaml."""
    required = {"target", "retry_task"}
    missing = required - sections.keys()
    if not missing:
        return
    msg = f"Manager prompt sections missing from prompts.yaml: {missing}"
    logger.bind(domain="manager").warning(msg)
    try:
        from vibe3.services.orchestra import ErrorTrackingService

        ErrorTrackingService.get_instance().record_error(
            error_code="E_CONFIG_MISSING",
            error_message=msg,
        )
    except Exception:
        pass


def build_manager_sync_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    flow_state: dict[str, object] | None,
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
    show_prompt: bool,
    tick_id: int = 0,
) -> ExecutionRequest:
    """Build the manager sync execution request using recipe-based prompt assembly."""
    _ = flow_state

    # Select variant based on session_id
    variant_key = "retry.resume" if session_id else "first.bootstrap"

    # Load prompts through template loader abstraction
    # NOTE: load_prompt_templates() provides graceful degradation if prompts.yaml
    # is missing (returns DEFAULT_PROMPT_TEMPLATES with empty manager section),
    # unlike the previous check_runtime_asset() which raised MissingResourceError.
    # This is intentional: manager request continues with incomplete prompts rather
    # than crashing the entire orchestration flow.
    prompts_data = load_prompt_templates()
    manager_sections = prompts_data.get("manager", {})
    _record_missing_manager_sections(manager_sections)

    # Build providers for static sections (no source override)
    providers: dict[str, PromptProvider] = {
        "manager.target": _make_section_provider(manager_sections, "manager.target"),
        "manager.quick_commands": _make_section_provider(
            manager_sections, "manager.quick_commands"
        ),
        "manager.retry_task": _make_section_provider(
            manager_sections, "manager.retry_task"
        ),
    }

    # Load manifest and get recipe definition with section sources
    manifest = PromptManifest.load_default()
    recipe_def = manifest.recipe("manager.default")

    # Check if recipe has loaded_definition with section sources
    if recipe_def.loaded_definition is not None:
        variant_spec = recipe_def.loaded_definition.variants.get(variant_key)
        if variant_spec is not None:
            # For sections with source declarations, resolve directly
            registry = ProviderRegistry()
            runtime_context: dict[str, Any] = {}

            # Create skill path resolver callback for prompts layer
            def skill_path_resolver(skill_name: str) -> str | None:
                result: str | None = get_resolver().get_skill_path(skill_name)
                return result

            for section_spec in variant_spec.sections:
                if section_spec.source is not None:
                    # Section has explicit source - resolve it
                    content = resolve_source(
                        section_spec.source,
                        runtime_context,
                        registry,
                        skill_path_resolver,
                    )

                    def _make_provider(c: str = content) -> str:
                        return c

                    providers[section_spec.key] = _make_provider

    # Render prompt using manifest
    prompt = manifest.render_sections(
        recipe_key="manager.default",
        variant_key=variant_key,
        providers=providers,
    )

    # Derive summary fields from variant_key and recipe sections
    prompt_mode = "retry" if session_id else "first"
    context_mode = "resume" if session_id else "bootstrap"
    variant_sections = []
    if recipe_def.loaded_definition is not None:
        variant_spec = recipe_def.loaded_definition.variants.get(variant_key)
        if variant_spec is not None:
            variant_sections = [
                s.key if hasattr(s, "key") else str(s) for s in variant_spec.sections
            ]
    dry_run_summary = {
        "prompt_mode": prompt_mode,
        "context_mode": context_mode,
        "session_reused": bool(session_id),
        "session_id": session_id or "",
        "sections": variant_sections,
        "refs": {"role": "manager", "issue": str(issue.number), "branch": branch},
    }

    # Collect and write provenance for dry-run audit
    if dry_run:
        provenance = collect_dry_run_provenance(
            manifest=manifest,
            recipe_key="manager.default",
            variant_key=variant_key,
            rendered_text=prompt,
        )
        provenance_path = write_prompt_provenance(
            provenance, role="manager", issue_number=issue.number
        )
        # Add provenance path to dry_run_summary
        dry_run_summary["provenance_path"] = str(provenance_path)

    manager_task = (
        "Act as the manager state controller. "
        "Inspect the scene, read issue comments and handoff, "
        "update labels/comments/handoff when allowed, "
        "and stop when the current state rule requires exit."
    )

    repo_root = Path(resolve_orchestra_repo_root())
    return build_issue_sync_prompt_request(
        role="manager",
        issue=issue,
        target_branch=branch,
        prompt=prompt,
        options=options,
        task=manager_task,
        actor=actor,
        execution_name=get_manager_session_name(issue.number),
        repo_path=repo_root,
        session_id=session_id,
        dry_run=dry_run,
        show_prompt=show_prompt,
        worktree_requirement=MANAGER_ROLE.worktree,
        dry_run_summary=dry_run_summary,
        tick_id=tick_id,
    )


MANAGER_SYNC_SPEC = IssueRoleSyncSpec(
    role_name="manager",
    resolve_options=resolve_manager_options,
    resolve_branch=MANAGER_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor, branch: build_manager_request(
        config,
        issue,
        branch=branch,
        repo_path=resolve_orchestra_repo_root(),
        actor=actor,
    ),
    build_sync_request=build_manager_sync_request,
    failure_handler=lambda issue_number, reason: fail_manager_issue(
        issue_number=issue_number,
        reason=reason,
    ),
)
