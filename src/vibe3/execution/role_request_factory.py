"""Modular factories for creating role-specific execution requests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.issue_role_support import (
    build_issue_async_cli_request,
    build_issue_sync_prompt_request,
)
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo


def build_role_async_request(
    *,
    role: str,
    config: OrchestraConfig,
    issue: IssueInfo,
    command_args: list[str],
    worktree_requirement: Any,
    branch: str | None = None,
    repo_path: Path | None = None,
    actor: str | None = None,
    refs: dict[str, str] | None = None,
) -> ExecutionRequest:
    """Unified factory for building role-specific async CLI requests."""
    target_branch = branch or f"task/issue-{issue.number}"
    effective_refs = {"issue_number": str(issue.number)}
    if refs:
        effective_refs.update(refs)

    actor = actor or f"orchestra:{role}"

    return build_issue_async_cli_request(
        role=role,
        issue=issue,
        target_branch=target_branch,
        command_args=command_args,
        actor=actor,
        execution_name=f"vibe3-{role}-issue-{issue.number}",
        refs=effective_refs,
        worktree_requirement=worktree_requirement,
        repo_path=repo_path,
    )


def build_role_sync_request(
    *,
    role: str,
    config: OrchestraConfig,
    issue: IssueInfo,
    branch: str,
    prompt: str,
    task: str,
    options: Any,
    worktree_requirement: Any,
    session_id: str | None = None,
    actor: str | None = None,
    dry_run: bool = False,
) -> ExecutionRequest:
    """Unified factory for building role-specific sync prompt requests."""
    actor = actor or f"orchestra:{role}"

    return build_issue_sync_prompt_request(
        role=role,
        issue=issue,
        target_branch=branch,
        prompt=prompt,
        options=options,
        task=task,
        actor=actor,
        execution_name=f"vibe3-{role}-issue-{issue.number}",
        session_id=session_id,
        dry_run=dry_run,
        worktree_requirement=worktree_requirement,
    )
