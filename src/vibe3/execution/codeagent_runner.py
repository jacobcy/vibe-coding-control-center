"""Sync codeagent execution utilities for command-mode role entrypoints."""

from dataclasses import dataclass
from pathlib import Path
from typing import cast

from loguru import logger
from typer import echo

from vibe3.agents.backends.codeagent import AgentResult, CodeagentBackend
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
from vibe3.execution.noop_gate import apply_unified_noop_gate, extract_state_label
from vibe3.execution.role_policy import (
    get_role_pre_gate_callback,
    get_role_section,
)
from vibe3.execution.session_service import load_session_id
from vibe3.models.review_runner import AgentOptions
from vibe3.services.handoff_service import HandoffService

__all__ = [
    "ExecutionRole",
    "CodeagentCommand",
    "CodeagentResult",
    "create_codeagent_command",
    "CodeagentExecutionService",
]


@dataclass
class SyncExecutionContext:
    """Execution context for sync execution shell."""

    options: AgentOptions
    session_id: str | None
    actor: str
    branch: str | None
    store: SQLiteClient | None
    before_state_label: str | None
    execution_cwd: Path


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

    def _prepare_sync_context(self, command: CodeagentCommand) -> SyncExecutionContext:
        """Prepare execution context before agent run."""
        log = logger.bind(
            domain="codeagent",
            role=command.role,
            handoff_kind=command.handoff_kind,
        )

        options = command.resolved_options or resolve_command_agent_options(
            config=self.config,
            section=get_role_section(command.role),
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

        # Capture before_state_label from GitHub for unified no-op gate.
        # Remote source of truth: GitHub issue labels, not local SQLite cache.
        before_state_label: str | None = None
        if command.issue_number is not None:
            try:
                from vibe3.clients.github_client import GitHubClient

                issue_payload = GitHubClient().view_issue(
                    command.issue_number,
                    repo=getattr(self.config, "repo", None),
                )
                if isinstance(issue_payload, dict):
                    before_state_label = extract_state_label(issue_payload)
            except Exception as exc:
                log.warning(f"Cannot read issue state for no-op gate: {exc}")

        execution_cwd = self._resolve_command_cwd(command.cwd)

        return SyncExecutionContext(
            options=options,
            session_id=session_id,
            actor=actor,
            branch=branch,
            store=store,
            before_state_label=before_state_label,
            execution_cwd=execution_cwd,
        )

    def _finalize_sync_execution(
        self,
        command: CodeagentCommand,
        ctx: SyncExecutionContext,
        agent_result: AgentResult,
    ) -> Path | None:
        """Finalize sync execution: handoff, lifecycle, callback, gate."""
        log = logger.bind(
            domain="codeagent",
            role=command.role,
            handoff_kind=command.handoff_kind,
        )

        effective_session_id = agent_result.session_id or ctx.session_id
        handoff_file = None

        if ctx.branch and ctx.store:
            persist_execution_lifecycle_event(
                ctx.store,
                ctx.branch,
                command.role,
                "completed",
                ctx.actor,
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
                        branch=ctx.branch,
                        actor=ctx.actor,
                        stdout=agent_result.stdout,
                    )
                except Exception as cb_exc:
                    log.warning(f"pre_gate_callback failed: {cb_exc}")

            # Unified no-op gate: single hard logic check after agent completion.
            # Executes ONLY if issue_number is available (worker roles).
            if command.issue_number is not None:
                apply_unified_noop_gate(
                    store=ctx.store,
                    issue_number=command.issue_number,
                    branch=ctx.branch,
                    actor=ctx.actor,
                    role=command.role,
                    before_state_label=ctx.before_state_label,
                    repo=getattr(self.config, "repo", None),
                )

            passive_kind = {"planner": "plan", "executor": "run"}.get(command.role)
            # Passive recording: record if NO active handoff happened this round
            if passive_kind and agent_result.stdout.strip() and handoff_file is None:
                try:
                    handoff_file = HandoffService(
                        store=ctx.store
                    ).record_passive_artifact(
                        kind=passive_kind,
                        content=agent_result.stdout,
                        actor=ctx.actor,
                        metadata=(
                            {"session_id": effective_session_id}
                            if effective_session_id
                            else None
                        ),
                        branch=ctx.branch,
                    )
                except Exception as exc:
                    log.warning(
                        f"Failed to record passive {passive_kind} artifact: {exc}"
                    )

        return handoff_file

    def execute_sync(self, command: CodeagentCommand) -> CodeagentResult:
        """Execute codeagent synchronously."""
        log = logger.bind(
            domain="codeagent",
            role=command.role,
            handoff_kind=command.handoff_kind,
        )

        ctx = self._prepare_sync_context(command)
        log.info("Starting sync execution")
        prompt_content = command.context_builder()
        echo(f"-> Executing with {ctx.options.agent or ctx.options.backend}...")

        try:
            agent_result = CodeagentBackend().run(
                prompt=prompt_content,
                options=ctx.options,
                task=command.task,
                dry_run=command.dry_run,
                session_id=ctx.session_id,
                cwd=ctx.execution_cwd,
                role=command.role,
                show_prompt=command.show_prompt,
                include_global_notice=command.include_global_notice,
                fallback_prompt=command.fallback_prompt,
                fallback_include_global_notice=command.fallback_include_global_notice,
                dry_run_summary=command.dry_run_summary,
            )
            if command.dry_run:
                return CodeagentResult(
                    success=True,
                    exit_code=agent_result.exit_code,
                    stdout=agent_result.stdout,
                    stderr=agent_result.stderr,
                    session_id=agent_result.session_id or ctx.session_id,
                )

            handoff_file = self._finalize_sync_execution(command, ctx, agent_result)
            effective_session_id = agent_result.session_id or ctx.session_id

            return CodeagentResult(
                success=agent_result.is_success(),
                exit_code=agent_result.exit_code,
                stdout=agent_result.stdout,
                stderr=agent_result.stderr,
                handoff_file=handoff_file,
                session_id=effective_session_id,
            )
        except BaseException as exc:
            if ctx.branch and ctx.store:
                abort_msg = (
                    f"{command.role.capitalize()} aborted "
                    f"(status: aborted, reason: {exc})"
                )
                from vibe3.exceptions import AgentExecutionError

                abort_refs: dict[str, str] = {"reason": str(exc), "status": "aborted"}
                if isinstance(exc, AgentExecutionError) and exc.log_path:
                    abort_refs["log_path"] = str(exc.log_path)
                persist_execution_lifecycle_event(
                    ctx.store,
                    ctx.branch,
                    command.role,
                    "aborted",
                    ctx.actor,
                    abort_msg,
                    session_id=ctx.session_id,
                    refs=abort_refs,
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
            show_prompt=request.show_prompt,
            include_global_notice=request.include_global_notice,
            fallback_prompt=request.fallback_prompt,
            fallback_include_global_notice=request.fallback_include_global_notice,
            dry_run_summary=request.dry_run_summary,
            pre_gate_callback=get_role_pre_gate_callback(role),
        )
        return self.execute_sync(command)
