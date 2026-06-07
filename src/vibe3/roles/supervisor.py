"""Supervisor role definitions and request builders."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vibe3.config import ConventionResolver

from vibe3.config import (
    SUPERVISOR_APPLY_GATE_CONFIG,
    SUPERVISOR_IDENTIFY_GATE_CONFIG,
    get_resolver,
)
from vibe3.execution import ExecutionRolePolicyService, use_current_branch
from vibe3.models import (
    ExecutionRequest,
    IssueInfo,
    OrchestraConfig,
    SupervisorIssueIdentified,
)
from vibe3.roles.definitions import IssueRoleSyncSpec, RoleDefinition
from vibe3.services import IssueFlowService, get_handoff_state_label

SUPERVISOR_IDENTIFY_ROLE = RoleDefinition(
    name="supervisor-identify",
    registry_role="supervisor",
    worktree=SUPERVISOR_IDENTIFY_GATE_CONFIG,
)

SUPERVISOR_APPLY_ROLE = RoleDefinition(
    name="supervisor-apply",
    registry_role="supervisor",
    worktree=SUPERVISOR_APPLY_GATE_CONFIG,
)


def build_supervisor_task_string(
    config: OrchestraConfig,
    issue_number: int,
    issue_title: str | None = None,
) -> str:
    """Build supervisor task description for issue processing.

    Args:
        config: Orchestra configuration
        issue_number: GitHub issue number
        issue_title: Optional issue title (used when known)

    Returns:
        Task description string
    """
    repo_hint = f" in repo {config.repo}" if config.repo else ""
    title = issue_title or f"issue #{issue_number}"
    return (
        f"Process governance issue #{issue_number}{repo_hint}: {title}\n"
        "This issue has already been handed to the configured supervisor material "
        "by the trigger layer.\n"
        "Read the issue directly, verify the findings, perform the "
        "allowed actions, "
        "comment the outcome on the same issue, and close it when complete."
    )


def build_supervisor_handoff_payload(
    config: OrchestraConfig,
    issue_number: int,
    issue_title: str | None = None,
    prompts_path: Path | None = None,
) -> tuple[str, Any, str]:
    """Build payload for supervisor handoff execution.

    Renders the supervisor prompt using direct recipe rendering.

    Returns:
        Tuple of (prompt, agent_options, task_string).
    """
    from vibe3.prompts.assembler import PromptAssembler
    from vibe3.prompts.manifest import PromptManifest
    from vibe3.prompts.models import PromptRecipe
    from vibe3.prompts.template_loader import DEFAULT_PROMPTS_PATH
    from vibe3.roles.governance import _build_runtime_registry

    prompts_path = prompts_path or DEFAULT_PROMPTS_PATH

    # Build empty snapshot context — supervisor handoff uses template rendering
    # without live snapshot data; the template embeds supervisor material.
    snapshot_context: dict[str, Any] = {
        "server_status": "running",
        "active_count": 0,
        "active_flows": 0,
        "active_worktrees": 0,
        "running_issue_count": 0,
        "queued_issue_count": 0,
        "suggested_issue_count": 0,
        "circuit_breaker_state": "closed",
        "circuit_breaker_failures": 0,
        "issue_list": "",
        "running_issue_details": "",
        "suggested_issue_details": "",
        "truncated_note": "",
    }

    # Load recipe from manifest
    manifest = PromptManifest.load_default()
    recipe_def = manifest.recipe("supervisor.handoff")

    if recipe_def.loaded_definition is None:
        raise ValueError("supervisor.handoff recipe not properly loaded")

    # Build PromptRecipe from loaded definition
    recipe = PromptRecipe(
        template_key=recipe_def.loaded_definition.template_key,
        variables=recipe_def.loaded_definition.variables,
        description=recipe_def.loaded_definition.description,
    )

    # Build registry for runtime providers declared by the recipe.
    registry = _build_runtime_registry(snapshot_context)
    assembler = PromptAssembler(prompts_path=prompts_path, registry=registry)
    rendered = assembler.render(recipe, runtime_context=snapshot_context)
    prompt = rendered.rendered_text

    options = ExecutionRolePolicyService(config).resolve_effective_agent_options(
        "supervisor"
    )
    task = build_supervisor_task_string(
        config,
        issue_number,
        issue_title,
    )

    return prompt, options, task


def build_supervisor_apply_request(
    config: OrchestraConfig,
    issue_number: int,
    issue_title: str | None = None,
    prompts_path: Path | None = None,
    actor: str = "orchestra:supervisor",
) -> ExecutionRequest:
    """Build the supervisor apply execution request.

    The temporary worktree is acquired automatically by ExecutionCoordinator
    based on worktree_requirement=TEMPORARY.

    Args:
        config: Orchestra configuration
        issue_number: Issue number to process
        issue_title: Optional issue title
        prompts_path: Optional path to prompt templates
        actor: Actor string for lifecycle tracking

    Returns:
        Fully populated ExecutionRequest for supervisor apply.
    """
    import os

    # Use IssueFlowService for canonical branch name
    issue_flow_service = IssueFlowService()
    branch = issue_flow_service.canonical_branch_name(issue_number)

    prompt, options, task = build_supervisor_handoff_payload(
        config,
        issue_number,
        issue_title,
        prompts_path,
    )

    return ExecutionRequest(
        role="supervisor",
        target_branch=branch,
        target_id=issue_number,
        execution_name=f"vibe3-supervisor-issue-{issue_number}",
        prompt=prompt,
        options=options,
        env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
        refs={"task": task, "issue_number": str(issue_number)},
        actor=actor,
        mode="async",
        worktree_requirement=SUPERVISOR_APPLY_ROLE.worktree,
    )


def build_supervisor_cli_request(
    config: OrchestraConfig,
    issue_number: int,
    issue_title: str | None = None,
    branch: str | None = None,
    actor: str = "cli:supervisor",
) -> ExecutionRequest:
    """Build supervisor apply request for CLI-driven invocation (no temp worktree).

    Used by the `internal apply` command where the user explicitly invokes
    the supervisor in their current workspace.

    Args:
        config: Orchestra configuration
        issue_number: Issue number to process
        issue_title: Optional issue title
        actor: Actor string for lifecycle tracking

    Returns:
        ExecutionRequest with worktree_requirement=NONE for CLI use.
    """
    import os

    if branch is None:
        # Use IssueFlowService for canonical branch name
        issue_flow_service = IssueFlowService()
        branch = issue_flow_service.canonical_branch_name(issue_number)

    prompt, options, task = build_supervisor_handoff_payload(
        config,
        issue_number,
        issue_title,
    )

    return ExecutionRequest(
        role="supervisor",
        target_branch=branch,
        target_id=issue_number,
        execution_name=f"vibe3-supervisor-issue-{issue_number}",
        prompt=prompt,
        options=options,
        env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
        refs={"task": task, "issue_number": str(issue_number)},
        actor=actor,
        mode="async",
        worktree_requirement=SUPERVISOR_IDENTIFY_ROLE.worktree,
    )


def build_supervisor_cli_sync_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    flow_state: dict[str, object] | None,
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
    show_prompt: bool,
) -> ExecutionRequest:
    """Build sync execution request for CLI-driven supervisor apply."""
    import os

    _ = flow_state

    prompt, _, task = build_supervisor_handoff_payload(
        config,
        issue.number,
        issue.title,
    )
    return ExecutionRequest(
        role="supervisor",
        target_branch=branch,
        target_id=issue.number,
        execution_name=f"vibe3-supervisor-issue-{issue.number}",
        prompt=prompt,
        options=options,
        refs={
            "task": task,
            "issue_number": str(issue.number),
            **({"session_id": session_id} if session_id else {}),
        },
        env={**os.environ},
        actor=actor,
        mode="sync",
        dry_run=dry_run,
        show_prompt=show_prompt,
        worktree_requirement=SUPERVISOR_IDENTIFY_ROLE.worktree,
    )


def resolve_supervisor_cli_options(
    config: OrchestraConfig,
    cli_overrides: dict[str, str] | None = None,
) -> Any:
    """Resolve supervisor options for issue-role CLI execution."""
    _ = cli_overrides
    return ExecutionRolePolicyService(config).resolve_effective_agent_options(
        "supervisor"
    )


SUPERVISOR_CLI_SYNC_SPEC = IssueRoleSyncSpec(
    role_name="supervisor",
    resolve_options=resolve_supervisor_cli_options,
    resolve_branch=use_current_branch,
    build_async_request=(
        lambda config, issue, actor, branch: build_supervisor_cli_request(
            config,
            issue.number,
            issue.title,
            branch=branch,
            actor=actor,
        )
    ),
    build_sync_request=build_supervisor_cli_sync_request,
)


def get_supervisor_prompt_path(
    resolver: ConventionResolver | None = None,
) -> str | None:
    """Get supervisor prompt path from profile.

    Args:
        resolver: Optional resolver (uses from_repo() if None)

    Returns:
        Path or None if profile has no supervisor
    """
    if resolver is None:
        resolver = get_resolver()
    result: str | None = resolver.get_supervisor_path("apply")
    return result


def iter_supervisor_identified_events(
    config: OrchestraConfig,
    raw_issues: Iterable[dict[str, object]],
) -> list[SupervisorIssueIdentified]:
    """Filter raw GitHub issues into supervisor observation events."""
    from loguru import logger

    issue_label = config.supervisor_handoff.issue_label
    handoff_label = get_handoff_state_label(config.supervisor_handoff)

    # Use profile resolution for supervisor template path
    resolver = get_resolver()
    supervisor_file = get_supervisor_prompt_path(resolver)

    if not supervisor_file:
        # No supervisor configured for current profile (minimal, github-flow)
        # Return empty list since these profiles don't have supervisor templates
        logger.warning(
            "No supervisor configured for current profile — "
            "skipping supervisor handoff events"
        )
        return []

    events: list[SupervisorIssueIdentified] = []
    for item in raw_issues:
        number = item.get("number")
        title = item.get("title")
        if not isinstance(number, int) or not isinstance(title, str):
            continue

        labels_raw = item.get("labels", [])
        labels: list[str] = []
        if isinstance(labels_raw, list):
            for lbl in labels_raw:
                if isinstance(lbl, dict):
                    name = lbl.get("name")
                    if isinstance(name, str):
                        labels.append(name)

        if issue_label not in labels or handoff_label not in labels:
            continue

        events.append(
            SupervisorIssueIdentified(
                issue_number=number,
                issue_title=title,
                supervisor_file=supervisor_file,
            )
        )
    return events
