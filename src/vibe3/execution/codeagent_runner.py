"""Sync codeagent execution utilities for command-mode role entrypoints."""

from pathlib import Path
from typing import Callable, Literal, cast

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
from vibe3.execution.contracts import ExecutionRequest
from vibe3.execution.execution_lifecycle import (
    execution_prefix,
    persist_execution_lifecycle_event,
)
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


def _resolve_request_pre_gate_callback(
    role: ExecutionRole,
) -> Callable[..., None] | None:
    """Resolve any role-specific callback that must run before the gate."""
    if role != "reviewer":
        return None

    from vibe3.roles.review import _process_review_sync_result

    return _process_review_sync_result


def _apply_unified_noop_gate(
    *,
    store: SQLiteClient,
    issue_number: int,
    branch: str,
    actor: str,
    role: ExecutionRole,
    before_state_label: str | None,
) -> None:
    """Apply the single hard no-op gate after agent completion.

    The only hard rule is simple:
    - if the agent did not change state_label, block
    - if the agent changed state_label, record the transition and pass

    Ref presence is observable metadata only. It must never advance state and it
    is no longer a separate blocking branch here.
    """
    from vibe3.services.issue_failure_service import (
        block_executor_noop_issue,
        block_manager_noop_issue,
        block_planner_noop_issue,
        block_reviewer_noop_issue,
    )
    from vibe3.utils.constants import EVENT_STATE_TRANSITIONED, EVENT_STATE_UNCHANGED

    flow_state = store.get_flow_state(branch)
    if not isinstance(flow_state, dict):
        return

    after_state_label = str(flow_state.get("state_label", "") or "")

    # Resolve role-specific block function
    if role == "manager":
        _block_fn = block_manager_noop_issue
    elif role == "planner":
        _block_fn = block_planner_noop_issue
    elif role == "executor":
        _block_fn = block_executor_noop_issue
    else:
        _block_fn = block_reviewer_noop_issue

    if before_state_label == after_state_label:
        state_desc = before_state_label or "(no state)"
        logger.bind(
            domain="codeagent",
            role=role,
            issue_number=issue_number,
            branch=branch,
        ).warning(
            f"No-op gate BLOCK: state unchanged after {role} " f"(still {state_desc})"
        )
        store.add_event(
            branch,
            EVENT_STATE_UNCHANGED,
            actor,
            detail=f"State unchanged after {role}: still {state_desc}",
            refs={
                "state": str(before_state_label or ""),
                "issue": str(issue_number),
            },
        )
        _block_fn(
            issue_number=issue_number,
            reason="state unchanged",
            actor=actor,
        )
        return

    logger.bind(
        domain="codeagent",
        role=role,
        issue_number=issue_number,
        branch=branch,
    ).info(
        f"No-op gate PASS: state changed {before_state_label} -> "
        f"{after_state_label}"
    )
    store.add_event(
        branch,
        EVENT_STATE_TRANSITIONED,
        actor,
        detail=f"State changed: {before_state_label} -> {after_state_label}",
        refs={
            "before_state": str(before_state_label or ""),
            "after_state": after_state_label,
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

        role_to_section: dict[str, Literal["manager", "plan", "run", "review"]] = {
            "manager": "manager",
            "planner": "plan",
            "executor": "run",
            "reviewer": "review",
        }
        options = command.resolved_options or resolve_command_agent_options(
            config=self.config,
            section=role_to_section[command.role],
            agent=command.agent,
            backend=command.backend,
            model=command.model,
        )
        session_id = command.session_id or load_session_id(command.role)
        actor = command.actor or format_agent_actor(options)
        branch = command.branch
        store = None
        if not command.dry_run and branch:
            try:
                store = SQLiteClient()
            except Exception as exc:  # pragma: no cover
                log.warning(f"Failed to initialize lifecycle store: {exc}")

        if branch and store:
            persist_execution_lifecycle_event(
                store,
                branch,
                command.role,
                "started",
                actor,
                f"{command.role.capitalize()} started (status: running)",
                session_id=session_id,
                event_type=f"codeagent_{execution_prefix(command.role)}_started",  # type: ignore[arg-type]
            )
            # Write latest_actor immediately so subsequent handoff
            # commands (e.g. `vibe3 handoff report`) resolve the
            # correct actor instead of a stale one.
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
                persist_execution_lifecycle_event(
                    store,
                    branch,
                    command.role,
                    "completed",
                    actor,
                    f"{command.role.capitalize()} completed (status: done)",
                    session_id=effective_session_id,
                    refs={"status": "completed"},
                    event_type=f"codeagent_{execution_prefix(command.role)}_completed",  # type: ignore[arg-type]
                )

                # pre_gate_callback: role-specific business callback that must
                # run BEFORE the gate (e.g., reviewer writes audit_ref from stdout).
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

                # Unified no-op gate: single hard logic check after agent completion.
                # Executes ONLY if issue_number is available (worker roles).
                if command.issue_number is not None:
                    _apply_unified_noop_gate(
                        store=store,
                        issue_number=command.issue_number,
                        branch=branch,
                        actor=actor,
                        role=command.role,
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
            if branch and store:
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
                    event_type=f"codeagent_{execution_prefix(command.role)}_aborted",  # type: ignore[arg-type]
                )
            raise

    def execute_sync_request(
        self,
        request: ExecutionRequest,
        *,
        cwd: Path | None = None,
    ) -> CodeagentResult:
        """Execute a sync worker request through the unified execution shell."""
        role = cast(ExecutionRole, request.role)
        command = create_codeagent_command(
            role=role,
            context_builder=lambda: request.prompt or "",
            task=request.refs.get("task"),
            dry_run=request.dry_run,
            branch=request.target_branch,
            issue_number=request.target_id,
            cwd=cwd,
            resolved_options=request.options,
            actor=request.actor,
            session_id=request.refs.get("session_id"),
            pre_gate_callback=_resolve_request_pre_gate_callback(role),
        )
        return self.execute_sync(command)
