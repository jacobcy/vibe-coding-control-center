"""Declarative role-service definitions for runtime registration.

These definitions make role dispatch explicit so runtime/server can register
services from shared config instead of depending on role-specific executors.
"""

from __future__ import annotations

import os
from pathlib import Path

from vibe3.clients.git_client import GitClient
from vibe3.environment.session_naming import get_manager_session_name
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.flow_dispatch import FlowManager
from vibe3.execution.roles import MANAGER_ROLE
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo


def resolve_orchestra_repo_root() -> Path:
    """Resolve shared repo root anchored at git common dir."""
    try:
        git_common_dir = GitClient().get_git_common_dir()
        if git_common_dir:
            return Path(git_common_dir).parent
    except Exception:
        pass
    return Path.cwd()


def build_manager_dispatch_request(
    config: OrchestraConfig,
    issue: IssueInfo,
    *,
    registry: SessionRegistryService | None = None,
    repo_path: Path | None = None,
    actor: str = "orchestra:manager",
) -> ExecutionRequest | None:
    """Build the manager execution request from declarative role policy."""
    flow_manager = FlowManager(config, registry=registry)
    try:
        flow = flow_manager.create_flow_for_issue(issue)
    except Exception:
        return None

    flow_branch = str(flow.get("branch") or "").strip()
    if not flow_branch:
        return None

    root = (repo_path or resolve_orchestra_repo_root()).resolve()
    env = dict(os.environ)
    env["VIBE3_ASYNC_CHILD"] = "1"
    if not env.get("VIBE3_MANAGER_BACKEND"):
        from vibe3.config.settings import VibeConfig
        from vibe3.runtime.agent_resolver import resolve_manager_agent_options

        try:
            options = resolve_manager_agent_options(config, VibeConfig.get_defaults())
            if options.backend:
                env["VIBE3_MANAGER_BACKEND"] = options.backend
            if options.model:
                env["VIBE3_MANAGER_MODEL"] = options.model
        except Exception:
            pass

    return ExecutionRequest(
        role="manager",
        target_branch=flow_branch,
        target_id=issue.number,
        execution_name=get_manager_session_name(issue.number),
        cmd=[
            "uv",
            "run",
            "--project",
            str(root),
            "python",
            "-I",
            str((root / "src" / "vibe3" / "cli.py").resolve()),
            "internal",
            "manager",
            str(issue.number),
            "--no-async",
        ],
        repo_path=str(root),
        env=env,
        refs={"issue_title": issue.title},
        actor=actor,
        mode="async",
        worktree_requirement=MANAGER_ROLE.gate_config.worktree,
    )
