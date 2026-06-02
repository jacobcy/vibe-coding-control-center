"""Manager role definition and request builder."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from vibe3.domain import FlowManager
from vibe3.environment.session_naming import get_manager_session_name
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.exceptions import CapacityDeferredError
from vibe3.execution import ExecutionRequest
from vibe3.execution.execution_role_policy import ExecutionRolePolicyService
from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
    build_task_flow_branch_resolver,
    resolve_orchestra_repo_root,
)
from vibe3.execution.role_contracts import MANAGER_GATE_CONFIG
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo, IssueState
from vibe3.prompts.manifest import PromptManifest, PromptProvider
from vibe3.prompts.template_loader import resolve_prompts_path
from vibe3.roles.definitions import (
    IssueRoleSyncSpec,
    RoleOutputContract,
    TriggerableRoleDefinition,
)
from vibe3.services.convention_resolver import ConventionResolver
from vibe3.services.issue_failure_service import fail_manager_issue

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


def resolve_manager_options(config: OrchestraConfig) -> Any:
    """Resolve manager agent options with env override support."""
    _backend_override = os.environ.get("VIBE3_MANAGER_BACKEND")
    _model_override = os.environ.get("VIBE3_MANAGER_MODEL") or None
    if _backend_override:
        from vibe3.models.review_runner import AgentOptions

        return AgentOptions(
            backend=_backend_override,
            model=_model_override,
        )

    # Validate assignee_dispatch configuration
    ad = config.assignee_dispatch
    if not ad.agent and not ad.backend:
        raise ValueError(
            "No assignee dispatch agent configuration found in "
            "orchestra.assignee_dispatch. Configure assignee_dispatch.agent or "
            "orchestra.assignee_dispatch.backend in settings.yaml."
        )

    return ExecutionRolePolicyService(config).resolve_effective_agent_options("manager")


MANAGER_BRANCH_RESOLVER = build_task_flow_branch_resolver(
    fallback_branch=lambda issue_number, _current_branch: ConventionResolver.from_repo()
    .resolve()
    .branch.canonical_branch(issue_number)
)


def _resolve_manager_token(config: OrchestraConfig) -> str | None:
    """Resolve manager token with fallback: env var (.zshrc) → keys.env → None."""
    token_env = config.assignee_dispatch.token_env
    if not token_env:
        return None

    # 1. Environment variable (set via .zshrc / direnv)
    token = os.getenv(token_env)
    if token:
        return token

    # 2. Fallback to config/keys.env
    try:
        from vibe3.execution.issue_role_support import resolve_orchestra_repo_root

        keys_path = resolve_orchestra_repo_root() / "config" / "keys.env"
        if keys_path.exists():
            prefix = f"{token_env}="
            for line in keys_path.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped.startswith(prefix) and not stripped.startswith("#"):
                    value = stripped[len(prefix) :].strip().strip("\"'")
                    if value:
                        logger.bind(domain="manager").debug(
                            f"Manager token loaded from {keys_path}"
                        )
                        return value
    except (OSError, UnicodeDecodeError) as e:
        logger.bind(domain="manager").debug(
            f"Failed to read keys.env for manager token: {e}"
        )

    return None


def _make_section_provider(
    manager_sections: dict[str, Any], section_key: str
) -> PromptProvider:
    """Create a provider that loads section from prompts.yaml."""

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
    registry: SessionRegistryService | None = None,
    repo_path: Path | None = None,
    actor: str = "orchestra:manager",
    tick_id: int = 0,
) -> ExecutionRequest | None:
    """Build the manager execution request from declarative role policy."""
    flow_manager = FlowManager(config, registry=registry)
    try:
        flow = flow_manager.create_flow_for_issue(issue)
    except CapacityDeferredError:
        # Re-raise capacity defer so handler can defer properly
        raise
    except Exception as exc:
        # Log full exception traceback
        logger.bind(
            domain="manager",
            issue_number=issue.number,
        ).exception(f"create_flow_for_issue failed: {exc}")

        # Record to error_log table (with guard to avoid masking original error)
        try:
            from vibe3.services.error_helpers import record_error

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

    flow_branch = str(flow.get("branch") or "").strip()
    if not flow_branch:
        return None

    refs = {"issue_title": issue.title}
    env = dict(os.environ)

    # Inject manager-specific token if configured (Phase 4)
    manager_token = _resolve_manager_token(config)
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

    # Inject manager backend/model if not already set
    if not env.get("VIBE3_MANAGER_BACKEND"):
        try:
            options = ExecutionRolePolicyService(
                config
            ).resolve_effective_agent_options("manager")
            if options.backend:
                env["VIBE3_MANAGER_BACKEND"] = options.backend
            if options.model:
                env["VIBE3_MANAGER_MODEL"] = options.model
        except Exception:
            logger.bind(domain="manager", issue_number=issue.number).debug(
                "Failed to resolve manager agent options, using defaults"
            )

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
        command_args=["internal", "manager", str(issue.number), "--no-async"],
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

    # Load prompts.yaml for static sections
    prompts_path = resolve_prompts_path()
    with open(prompts_path) as f:
        prompts_data = yaml.safe_load(f)
    manager_sections = prompts_data.get("manager", {})

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
            from vibe3.prompts.builtin_providers import resolve_source
            from vibe3.prompts.provider_registry import ProviderRegistry

            registry = ProviderRegistry()
            runtime_context: dict[str, Any] = {}

            # Create skill path resolver callback for prompts layer
            def skill_path_resolver(skill_name: str) -> str | None:
                return ConventionResolver.from_repo().get_skill_path(skill_name)

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
        tick_id=tick_id,
    )


MANAGER_SYNC_SPEC = IssueRoleSyncSpec(
    role_name="manager",
    resolve_options=resolve_manager_options,
    resolve_branch=MANAGER_BRANCH_RESOLVER,
    build_async_request=lambda config, issue, actor: build_manager_request(
        config,
        issue,
        repo_path=resolve_orchestra_repo_root(),
        actor=actor,
    ),
    build_sync_request=build_manager_sync_request,
    failure_handler=lambda issue_number, reason: fail_manager_issue(
        issue_number=issue_number,
        reason=reason,
    ),
)
