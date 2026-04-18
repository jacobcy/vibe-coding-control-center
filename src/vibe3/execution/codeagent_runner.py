"""Sync codeagent execution utilities for command-mode role entrypoints."""

import os
from pathlib import Path
from typing import Literal

from loguru import logger
from typer import echo

from vibe3.agents.backends.codeagent import CodeagentBackend
from vibe3.agents.models import (
    CodeagentCommand,
    CodeagentResult,
    ExecutionRole,
    create_codeagent_command,
)
from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.config.settings import VibeConfig
from vibe3.execution.actor_support import format_agent_actor
from vibe3.execution.codeagent_support import resolve_command_agent_options
from vibe3.execution.execution_lifecycle import persist_execution_lifecycle_event
from vibe3.execution.session_service import load_session_id
from vibe3.services.handoff_recorder_unified import (
    HandoffRecord,
    record_handoff_unified,
)

__all__ = [
    "ExecutionRole",
    "CodeagentCommand",
    "CodeagentResult",
    "create_codeagent_command",
    "CodeagentExecutionService",
]

_REQUIRED_REF_BY_ROLE: dict[ExecutionRole, str] = {
    "planner": "plan_ref",
    "executor": "report_ref",
    "reviewer": "audit_ref",
}


def _apply_unified_noop_gate(
    *,
    store: SQLiteClient,
    issue_number: int,
    branch: str,
    actor: str,
    role: ExecutionRole,
    required_ref: str,
    before_state_label: str | None,
) -> None:
    """Apply the unified three-branch no-op gate after agent completion.

    This gate fires inside codeagent_runner for BOTH sync and async paths,
    ensuring consistent completion checking regardless of dispatch mode.

    Three-branch logic:
    1. Missing required_ref -> block
    2. Ref present + state unchanged -> block (no-op)
    3. Ref present + state changed -> pass (record transition)
    """
    from vibe3.services.issue_failure_service import (
        block_executor_noop_issue,
        block_planner_noop_issue,
        block_reviewer_noop_issue,
    )
    from vibe3.utils.constants import EVENT_STATE_TRANSITIONED, EVENT_STATE_UNCHANGED

    flow_state = store.get_flow_state(branch)
    if not isinstance(flow_state, dict):
        return

    after_state_label = str(flow_state.get("state_label", "") or "")
    ref_value = str(flow_state.get(required_ref, "") or "")

    _block_fn = {
        "planner": block_planner_noop_issue,
        "executor": block_executor_noop_issue,
        "reviewer": block_reviewer_noop_issue,
    }[role]

    # Branch 1: Missing required_ref -> block
    if not ref_value:
        store.add_event(
            branch,
            EVENT_STATE_UNCHANGED,
            actor,
            detail=f"Missing {required_ref} after {role} -> blocked",
            refs={
                "state": str(before_state_label or ""),
                "required_ref": required_ref,
                "issue": str(issue_number),
            },
        )
        _block_fn(
            issue_number=issue_number,
            reason=f"{role} completed without producing {required_ref}",
            actor=actor,
        )
        return

    # Branch 2: Ref present + state unchanged -> block (no-op)
    if before_state_label == after_state_label:
        store.add_event(
            branch,
            EVENT_STATE_UNCHANGED,
            actor,
            detail=(
                f"State unchanged after {required_ref} gate: "
                f"still {before_state_label}"
            ),
            refs={
                "state": str(before_state_label or ""),
                "required_ref": required_ref,
                "issue": str(issue_number),
            },
        )
        _block_fn(
            issue_number=issue_number,
            reason=f"{required_ref} present but state unchanged",
            actor=actor,
        )
        return

    # Branch 3: Ref present + state changed -> pass
    store.add_event(
        branch,
        EVENT_STATE_TRANSITIONED,
        actor,
        detail=f"State changed: {before_state_label} -> {after_state_label}",
        refs={
            "before_state": str(before_state_label or ""),
            "after_state": after_state_label,
            "required_ref": required_ref,
            "issue": str(issue_number),
        },
    )


class CodeagentExecutionService:
    """Unified sync execution shell for command-mode codeagent runs."""

    def __init__(self, config: VibeConfig | None = None) -> None:
        self.config = config or VibeConfig.get_defaults()

    @staticmethod
    def _resolve_command_cwd(explicit_cwd: Path | None) -> Path:
        if explicit_cwd is not None:
            return explicit_cwd
        try:
            return Path(GitClient().get_worktree_root())
        except Exception:
            return Path.cwd()

    def execute_sync(self, command: CodeagentCommand) -> CodeagentResult:
        """Execute codeagent synchronously."""
        log = logger.bind(
            domain="codeagent",
            role=command.role,
            handoff_kind=command.handoff_kind,
        )

        role_to_section: dict[str, Literal["plan", "run", "review"]] = {
            "planner": "plan",
            "executor": "run",
            "reviewer": "review",
        }
        options = resolve_command_agent_options(
            config=self.config,
            section=role_to_section[command.role],
            agent=command.agent,
            backend=command.backend,
            model=command.model,
        )
        session_id = load_session_id(command.role)
        actor = format_agent_actor(options)
        is_async_child = os.environ.get("VIBE3_ASYNC_CHILD") == "1"
        branch = command.branch
        store = None
        if not command.dry_run and branch:
            try:
                store = SQLiteClient()
            except Exception as exc:  # pragma: no cover
                log.warning(f"Failed to initialize lifecycle store: {exc}")

        if branch and store:
            if not is_async_child:
                persist_execution_lifecycle_event(
                    store,
                    branch,
                    command.role,
                    "started",
                    actor,
                    f"{command.role.capitalize()} started (status: running)",
                    session_id=session_id,
                )
            # Write latest_actor immediately so subsequent handoff
            # commands (e.g. `vibe3 handoff report`) resolve the
            # correct actor instead of a stale one.
            # Must execute in both sync and async child paths
            # because the inner child has the real agent actor.
            store.update_flow_state(branch, latest_actor=actor)

        # Capture before_state_label for unified no-op gate.
        # Runs in both sync and async paths when issue_number is available.
        before_state_label: str | None = None
        if branch and store and command.issue_number is not None:
            flow_state = store.get_flow_state(branch)
            if isinstance(flow_state, dict):
                before_state_label = str(flow_state.get("state_label", "") or "")

        log.info("Starting sync execution")
        prompt_content = command.context_builder()
        execution_cwd = self._resolve_command_cwd(command.cwd)
        echo(f"-> Executing with {options.agent or options.backend}...")

        try:
            agent_result = CodeagentBackend().run(
                prompt=prompt_content,
                options=options,
                task=command.task,
                dry_run=command.dry_run,
                session_id=session_id,
                cwd=execution_cwd,
            )
            if command.dry_run:
                return CodeagentResult(
                    success=True,
                    exit_code=agent_result.exit_code,
                    stdout=agent_result.stdout,
                    stderr=agent_result.stderr,
                    session_id=agent_result.session_id or session_id,
                )

            effective_session_id = agent_result.session_id or session_id
            handoff_file = record_handoff_unified(
                HandoffRecord(
                    kind=command.handoff_kind,  # type: ignore[arg-type]
                    content=agent_result.stdout,
                    options=options,
                    session_id=effective_session_id,
                    metadata=command.handoff_metadata,
                    branch=command.branch,
                )
            )
            if handoff_file:
                echo(f"-> {command.handoff_kind.capitalize()} saved: {handoff_file}")

            if branch and store:
                if not is_async_child:
                    persist_execution_lifecycle_event(
                        store,
                        branch,
                        command.role,
                        "completed",
                        actor,
                        f"{command.role.capitalize()} completed (status: done)",
                        session_id=effective_session_id,
                        refs={"status": "completed"},
                    )

                # Pre-gate callback: allow roles to write refs from stdout
                # before the gate checks. Used by reviewer to write audit_ref.
                if (
                    command.pre_gate_callback is not None
                    and command.issue_number is not None
                    and agent_result.stdout
                ):
                    try:
                        command.pre_gate_callback(
                            issue_number=command.issue_number,
                            branch=branch,
                            actor=actor,
                            stdout=agent_result.stdout,
                        )
                    except Exception as cb_exc:
                        log.warning(f"pre_gate_callback failed: {cb_exc}")

                # Unified no-op gate: fires in both sync and async paths.
                # Checks required_ref presence and state_label change.
                # Blocks the issue if the agent produced no observable progress.
                required_ref = _REQUIRED_REF_BY_ROLE.get(command.role)
                if command.issue_number is not None and required_ref:
                    _apply_unified_noop_gate(
                        store=store,
                        issue_number=command.issue_number,
                        branch=branch,
                        actor=actor,
                        role=command.role,
                        required_ref=required_ref,
                        before_state_label=before_state_label,
                    )

            return CodeagentResult(
                success=agent_result.is_success(),
                exit_code=agent_result.exit_code,
                stdout=agent_result.stdout,
                stderr=agent_result.stderr,
                handoff_file=handoff_file,
                session_id=effective_session_id,
            )
        except BaseException as exc:
            if branch and store and not is_async_child:
                abort_msg = (
                    f"{command.role.capitalize()} aborted "
                    f"(status: aborted, reason: {exc})"
                )
                persist_execution_lifecycle_event(
                    store,
                    branch,
                    command.role,
                    "aborted",
                    actor,
                    abort_msg,
                    session_id=session_id,
                    refs={"reason": str(exc), "status": "aborted"},
                )
            raise
