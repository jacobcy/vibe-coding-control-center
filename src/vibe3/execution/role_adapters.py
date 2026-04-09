"""Role adapters for building execution requests.

These adapters translate role-specific requirements into unified ExecutionRequest
objects, focusing on what's different about each role rather than managing
the entire execution framework.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from loguru import logger

from vibe3.execution.contracts import ExecutionRequest
from vibe3.manager.command_builder import CommandBuilder
from vibe3.manager.flow_manager import FlowManager
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.models.orchestration import IssueInfo

if TYPE_CHECKING:
    from vibe3.environment.session_registry import SessionRegistryService


class ManagerRoleAdapter:
    """Adapter for manager-specific execution requirements.

    This adapter handles:
    - Flow/scene creation and binding
    - Worktree resolution
    - Manager command/env assembly
    - Manager gate configuration

    It does NOT handle:
    - Capacity checking (ExecutionCoordinator's job)
    - Session lifecycle (ExecutionCoordinator's job)
    - Actual execution (ExecutionCoordinator's job)
    """

    def __init__(
        self,
        config: OrchestraConfig,
        registry: Optional["SessionRegistryService"] = None,
        repo_path: Optional[Path] = None,
    ):
        self.config = config
        self.repo_path = repo_path or Path.cwd()
        self.flow_manager = FlowManager(config, registry=registry)
        self.command_builder = CommandBuilder(config)

    def prepare_execution_request(
        self,
        issue: IssueInfo,
        dry_run: bool = False,
    ) -> Optional[ExecutionRequest]:
        """Prepare execution request for manager dispatch.

        This method handles manager-specific setup (flow, worktree, command)
        and returns an ExecutionRequest ready for ExecutionCoordinator.

        Args:
            issue: Issue to dispatch manager for
            dry_run: If True, skip actual dispatch

        Returns:
            ExecutionRequest if successful, None if preparation failed
        """
        log = logger.bind(
            domain="manager_adapter",
            issue=issue.number,
        )

        # 1. Create flow
        try:
            flow = self.flow_manager.create_flow_for_issue(issue)
            flow_branch = str(flow.get("branch") or "").strip()
            if not flow_branch:
                log.error("Flow branch missing after creation")
                return None
        except Exception as exc:
            log.error(f"Failed to create flow: {exc}")
            return None

        # 2. Resolve worktree
        manager_cwd = self._resolve_manager_cwd(issue.number, flow_branch)
        if not manager_cwd:
            log.error("Failed to resolve worktree")
            return None

        log.info(f"Manager will use worktree: {manager_cwd}")

        # 3. Build command and env
        cmd = self.command_builder.build_manager_command(issue)
        env = self._build_manager_env()

        # 4. Build execution request
        execution_name = f"manager-{issue.number}-{flow_branch}"

        return ExecutionRequest(
            role="manager",
            target_branch=flow_branch,
            target_id=issue.number,
            execution_name=execution_name,
            cmd=cmd,
            cwd=str(manager_cwd),
            env=env,
            refs={"issue_title": issue.title},
            actor="orchestra:manager",
            mode="async",
            dry_run=dry_run,
        )

    def _resolve_manager_cwd(self, issue_number: int, branch: str) -> Optional[Path]:
        """Resolve worktree path for manager execution.

        Manager needs a worktree aligned to scene_base_ref.
        """
        from vibe3.environment.worktree import WorktreeManager

        worktree_manager = WorktreeManager(
            self.config,
            self.repo_path,
            self.flow_manager,
        )

        try:
            # Manager needs permanent worktree - use _find_worktree_for_branch
            cwd = worktree_manager._find_worktree_for_branch(branch)
            if cwd:
                # Align to scene base
                if worktree_manager.align_auto_scene_to_base(cwd, branch):
                    return cwd
        except Exception as exc:
            logger.bind(
                domain="manager_adapter",
                issue=issue_number,
            ).exception(f"Failed to resolve worktree: {exc}")

        return None

    def _build_manager_env(self) -> Dict[str, str]:
        """Build environment variables for manager execution."""
        env = dict(os.environ)
        env["VIBE3_ASYNC_CHILD"] = "1"

        # Add manager-specific config if available
        from vibe3.config.settings import VibeConfig
        from vibe3.runtime.agent_resolver import resolve_manager_agent_options

        try:
            options = resolve_manager_agent_options(
                self.config,
                VibeConfig.get_defaults(),
            )
            if options.backend:
                env["VIBE3_MANAGER_BACKEND"] = options.backend
            if options.model:
                env["VIBE3_MANAGER_MODEL"] = options.model
        except Exception:
            pass

        return env

    def check_no_op_gate(self, issue_number: int, result: Any) -> bool:
        """Check if manager execution produced actual changes.

        This is the manager-specific "no-op gate" - manager must not
        complete without making any changes.

        Args:
            issue_number: Issue number
            result: Execution result

        Returns:
            True if execution was valid (not a no-op), False if no-op
        """
        # TODO: Implement no-op detection based on execution result
        # For now, assume valid execution
        return True
