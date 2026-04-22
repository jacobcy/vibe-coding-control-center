"""Supervisor role definitions and request builders."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from vibe3.domain.events.supervisor_apply import SupervisorIssueIdentified
from vibe3.execution.agent_resolver import resolve_supervisor_agent_options
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.issue_role_support import use_current_branch
from vibe3.execution.role_contracts import (
    SUPERVISOR_APPLY_GATE_CONFIG,
    SUPERVISOR_IDENTIFY_GATE_CONFIG,
)
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo
from vibe3.roles.definitions import IssueRoleSyncSpec, RoleDefinition

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
    supervisor_file = config.supervisor_handoff.supervisor_file
    return (
        f"Process governance issue #{issue_number}{repo_hint}: {title}\n"
        f"This issue has already been handed to {supervisor_file} by the "
        "trigger layer.\n"
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

    Renders the supervisor prompt using governance prompt infrastructure
    with supervisor-handoff config overrides.

    Returns:
        Tuple of (prompt, agent_options, task_string).
    """
    from vibe3.roles.governance import render_governance_prompt

    governance_cfg = config.governance.model_copy(
        update={
            "supervisor_file": config.supervisor_handoff.supervisor_file,
            "supervisor_files": [],
            "prompt_template": config.supervisor_handoff.prompt_template,
            "include_supervisor_content": True,
            "dry_run": False,
        }
    )
    handoff_config = config.model_copy(update={"governance": governance_cfg})

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

    rendered = render_governance_prompt(handoff_config, snapshot_context, prompts_path)
    prompt = rendered.rendered_text
    options = resolve_supervisor_agent_options(config)
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

    prompt, options, task = build_supervisor_handoff_payload(
        config,
        issue_number,
        issue_title,
        prompts_path,
    )

    return ExecutionRequest(
        role="supervisor",
        target_branch=f"issue-{issue_number}",
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

    prompt, options, task = build_supervisor_handoff_payload(
        config,
        issue_number,
        issue_title,
    )

    return ExecutionRequest(
        role="supervisor",
        target_branch=f"issue-{issue_number}",
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
    session_id: str | None,
    options: Any,
    actor: str,
    dry_run: bool,
) -> ExecutionRequest:
    """Build sync execution request for CLI-driven supervisor apply."""
    import os

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
        worktree_requirement=SUPERVISOR_IDENTIFY_ROLE.worktree,
    )


SUPERVISOR_CLI_SYNC_SPEC = IssueRoleSyncSpec(
    role_name="supervisor",
    resolve_options=resolve_supervisor_agent_options,
    resolve_branch=use_current_branch,
    build_async_request=lambda config, issue, actor: build_supervisor_cli_request(
        config,
        issue.number,
        issue.title,
        actor=actor,
    ),
    build_sync_request=build_supervisor_cli_sync_request,
)


def iter_supervisor_identified_events(
    config: OrchestraConfig,
    raw_issues: Iterable[dict[str, object]],
) -> list[SupervisorIssueIdentified]:
    """Filter raw GitHub issues into supervisor observation events."""
    issue_label = config.supervisor_handoff.issue_label
    handoff_label = config.supervisor_handoff.handoff_state_label
    supervisor_file = config.supervisor_handoff.supervisor_file

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
