"""Sync codeagent execution utilities for command-mode role entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from loguru import logger
from typer import echo

from vibe3.clients.git_client import GitClient
from vibe3.clients.sqlite_client import SQLiteClient

if TYPE_CHECKING:
    from loguru import Logger

    from vibe3.agents.backends.codeagent import AgentResult
    from vibe3.agents.models import (
        CodeagentCommand,
        CodeagentResult,
    )
    from vibe3.exceptions.error_severity import ErrorSeverity
from vibe3.config.role_policy import get_role_section
from vibe3.config.settings import VibeConfig
from vibe3.execution.codeagent_support import resolve_command_agent_options
from vibe3.execution.execution_lifecycle import (
    execution_prefix,
    persist_execution_lifecycle_event,
)
from vibe3.execution.noop_gate import apply_unified_noop_gate
from vibe3.execution.session_service import load_session_id
from vibe3.models.execution_request import ExecutionRequest
from vibe3.models.review_runner import AgentOptions
from vibe3.services.actor_support import format_agent_actor
from vibe3.services.handoff_service import HandoffService


def _severity_event_type(role: str, severity: "ErrorSeverity") -> str:
    """Build event type suffix based on error severity."""
    from vibe3.exceptions.error_severity import ErrorSeverity

    prefix = execution_prefix(role)  # type: ignore[arg-type]
    if severity == ErrorSeverity.WARNING:
        return f"codeagent_{prefix}_warning"
    elif severity == ErrorSeverity.CRITICAL:
        return f"codeagent_{prefix}_aborted"
    else:  # ERROR
        return f"codeagent_{prefix}_error"


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
    commit_count_before: int | None = None
    before_issue_is_closed: bool = False


class CodeagentExecutionService:
    """Unified sync execution shell for command-mode codeagent runs."""

    def __init__(self, config: VibeConfig | None = None) -> None:
        self.config = config or VibeConfig.get_defaults()

    @staticmethod
    def _cleanup_supervisor_handoff_label(
        issue_number: int,
        actor: str,
        log: "Logger",
    ) -> None:
        """Remove state/handoff label to prevent supervisor re-dispatch.

        Supervisor (L2) has no flow/state machine. After execution
        (success or failure), we remove the handoff trigger label so
        the next tick does not re-dispatch the same issue.
        """
        from vibe3.clients.github_labels import GhIssueLabelPort
        from vibe3.config.orchestra_settings import load_orchestra_config
        from vibe3.services.orchestra_helpers import get_handoff_state_label

        config = load_orchestra_config()
        handoff_label = get_handoff_state_label(config.supervisor_handoff)

        try:
            repo = config.repo
            labels_client = GhIssueLabelPort(repo=repo)
            labels_client.remove_issue_label(issue_number, handoff_label)
            log.info(f"Removed {handoff_label} label from #{issue_number}")
        except Exception as exc:
            log.warning(
                f"Failed to remove {handoff_label} label from "
                f"#{issue_number}: {exc}"
            )

    @staticmethod
    def _check_planner_commits(
        commit_count_before: int,
        branch: str | None,
        actor: str,
        log: "Logger",
        execution_cwd: Path | None = None,
    ) -> None:
        """Check for unauthorized commits by planner.

        Planner should only create docs/plans/ or docs/reports/ changes. If we detect
        commits outside these directories, log a warning and record a finding.
        """
        if not branch:
            return

        try:
            # Get current commit count
            result = GitClient(cwd=execution_cwd)._run(["rev-list", "--count", "HEAD"])
            commit_count_after = int(result.strip())

            if commit_count_after > commit_count_before:
                # New commits detected - check what changed
                commits_diff = commit_count_after - commit_count_before
                log.info(
                    f"Planner created {commits_diff} new commit(s) — "
                    "checking files for policy compliance"
                )

                # Get the list of changed files in new commits
                # Use HEAD~N..HEAD to get changes in last N commits
                result = GitClient(cwd=execution_cwd)._run(
                    [
                        "diff",
                        f"HEAD~{commits_diff}",
                        "HEAD",
                        "--name-only",
                    ]
                )
                changed_files = result.strip().split("\n") if result.strip() else []

                # Check if any files are outside docs/plans/ and docs/reports/
                unauthorized_files = [
                    f
                    for f in changed_files
                    if f
                    and not (
                        f.startswith("docs/plans/") or f.startswith("docs/reports/")
                    )
                ]

                if unauthorized_files:
                    log.warning(
                        f"Unauthorized file changes detected: {unauthorized_files}"
                    )

                    # Record finding to handoff
                    finding_message = (
                        f"Planner created {commits_diff} unauthorized commit(s) "
                        f"with files outside docs/plans/ and docs/reports/: "
                        f"{unauthorized_files}"
                    )
                    try:
                        HandoffService().append_current_handoff(
                            message=finding_message,
                            kind="finding",
                            actor=actor,
                            branch=branch,
                        )
                    except Exception as exc:
                        log.warning(f"Failed to record planner finding: {exc}")
                else:
                    # All changes are in allowed directories
                    log.info(
                        f"Planner created {commits_diff} commit(s) with only "
                        "authorized files (docs/plans/ or docs/reports/)"
                    )
        except Exception as exc:
            log.warning(f"Failed to check planner commits: {exc}")

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
        # Also capture whether the issue is closed before agent execution.
        before_state_label: str | None = None
        before_issue_is_closed = False
        if command.issue_number is not None:
            try:
                from vibe3.clients.github_client import GitHubClient

                issue_payload = GitHubClient().view_issue(
                    command.issue_number,
                    repo=getattr(self.config, "repo", None),
                )
                if isinstance(issue_payload, dict):
                    # Extract state label
                    labels = issue_payload.get("labels", [])
                    if isinstance(labels, list):
                        for label in labels:
                            if isinstance(label, dict):
                                name = label.get("name")
                                if isinstance(name, str) and name.startswith("state/"):
                                    before_state_label = name
                                    break
                    # Check if issue is closed
                    if str(issue_payload.get("state", "")).upper() == "CLOSED":
                        before_issue_is_closed = True
            except Exception as exc:
                log.warning(f"Cannot read issue state for no-op gate: {exc}")

        execution_cwd = self._resolve_command_cwd(command.cwd)

        # Record commit count before execution (for planner commit detection)
        commit_count_before: int | None = None
        if command.role == "planner":
            try:
                result = GitClient(cwd=execution_cwd)._run(
                    ["rev-list", "--count", "HEAD"]
                )
                commit_count_before = int(result.strip())
            except Exception as exc:
                log.warning(f"Failed to record commit count before execution: {exc}")

        return SyncExecutionContext(
            options=options,
            session_id=session_id,
            actor=actor,
            branch=branch,
            store=store,
            before_state_label=before_state_label,
            execution_cwd=execution_cwd,
            commit_count_before=commit_count_before,
            before_issue_is_closed=before_issue_is_closed,
        )

    def _finalize_sync_execution(
        self,
        command: CodeagentCommand,
        ctx: SyncExecutionContext,
        agent_result: AgentResult,
    ) -> Path | None:
        """Finalize sync execution: handoff, lifecycle, gate."""

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

            # Read flow state ONCE here, used by both gate check and passive recording
            flow_state = ctx.store.get_flow_state(ctx.branch) if ctx.store else {}

            # Planner commit detection: check for unauthorized commits
            if command.role == "planner" and ctx.commit_count_before is not None:
                self._check_planner_commits(
                    ctx.commit_count_before,
                    ctx.branch,
                    ctx.actor,
                    log,
                    execution_cwd=ctx.execution_cwd,
                )

            # Unified no-op gate: single hard logic check after agent completion.
            # Executes ONLY for L3 worker roles (manager/planner/executor/reviewer).
            # Supervisor (L2) is lightweight: no flow, no state machine, skip gate.
            _noop_gate_roles = {"manager", "planner", "executor", "reviewer"}
            if command.issue_number is not None and command.role in _noop_gate_roles:
                apply_unified_noop_gate(
                    store=ctx.store,
                    issue_number=command.issue_number,
                    branch=ctx.branch,
                    actor=ctx.actor,
                    role=command.role,
                    before_state_label=ctx.before_state_label,
                    repo=getattr(self.config, "repo", None),
                    flow_state=flow_state,
                    tick_id=command.tick_id,
                    before_issue_is_closed=ctx.before_issue_is_closed,
                )

                # Persist transition_count after gate call
                # Note: retry counters are persisted inside noop_gate itself
                if flow_state and "transition_count" in flow_state:
                    ctx.store.update_flow_state(
                        ctx.branch, transition_count=flow_state["transition_count"]
                    )

            # Supervisor success: remove state/handoff label to prevent re-dispatch.
            # Agent is expected to close the issue, but we ensure label cleanup.
            if command.role == "supervisor" and command.issue_number is not None:
                self._cleanup_supervisor_handoff_label(
                    command.issue_number, ctx.actor, log
                )

            passive_kind = {"planner": "plan", "executor": "run"}.get(command.role)
            # Passive recording: when no active handoff occurred this round
            # (i.e., agent did NOT call `handoff plan` or `handoff report`)
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
        from vibe3.agents.backends.codeagent import CodeagentBackend
        from vibe3.agents.models import CodeagentResult

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
        except Exception as exc:
            from vibe3.exceptions import AgentExecutionError
            from vibe3.exceptions.error_classification import (
                classify_error_hybrid,
                get_error_handling_contract,
            )
            from vibe3.services.error_helpers import record_error

            # Classify error and record to SQLite for threshold tracking.
            # FailedGate.check() reads SQLite error_log on next heartbeat tick.
            error_code = classify_error_hybrid(exc)

            # Get handling contract for severity-aware behavior
            error_contract = get_error_handling_contract(error_code)

            # Use store-specific instance to ensure consistency with FailedGate
            # Record error with severity from contract
            record_error(
                error_code=error_code,
                error_message=str(exc),
                store=ctx.store,
                tick_id=command.tick_id,
                issue_number=command.issue_number,
                branch=command.branch,
                severity=error_contract.severity,
            )

            # Build abort message
            abort_msg = (
                f"{command.role.capitalize()} aborted "
                f"(status: blocked, error: {error_code})"
            )

            # Record abort event to flow timeline
            if ctx.branch and ctx.store:
                abort_refs: dict[str, str] = {
                    "reason": str(exc),
                    "error_code": error_code,
                    "status": "blocked",
                }
                if isinstance(exc, AgentExecutionError) and exc.log_path:
                    abort_refs["log_path"] = str(exc.log_path)

                # Build severity-aware event type
                event_type = _severity_event_type(command.role, error_contract.severity)
                persist_execution_lifecycle_event(
                    ctx.store,
                    ctx.branch,
                    command.role,
                    "aborted",
                    ctx.actor,
                    abort_msg,
                    session_id=ctx.session_id,
                    refs=abort_refs,
                    event_type=event_type,
                )

            # Runtime error handling: record to error_log only.
            # Supervisor (L2) uses lightweight failure: remove handoff label.
            # All runtime errors do NOT trigger flow block.
            # Flow block is determined by business logic only
            # (noop_gate, dependencies, loops).
            # FailedGate controls dispatch based on error severity.
            if command.issue_number is not None:
                if command.role == "supervisor":
                    self._cleanup_supervisor_handoff_label(
                        command.issue_number,
                        ctx.actor,
                        log,
                    )
                # All runtime errors only record to error_log.
                # They do NOT trigger flow block.
                # Flow block is determined by business logic only
                # (noop_gate, dependencies, loops).
                # FailedGate controls dispatch based on error severity.
                if error_contract.issue_action == "record_only":
                    logger.bind(
                        domain="codeagent",
                        role=command.role,
                        issue_number=command.issue_number,
                        error_code=error_code,
                        severity=error_contract.severity.value,
                    ).info(
                        f"Runtime error recorded: {error_code} "
                        f"({error_contract.severity.value}) - "
                        "FailedGate controls dispatch, "
                        "noop_gate checks business progress"
                    )
                else:
                    # Should not reach here: all runtime errors
                    # now use "record_only" since flow block and
                    # error tracking are orthogonal systems.
                    logger.bind(
                        domain="codeagent",
                        role=command.role,
                        issue_number=command.issue_number,
                        error_code=error_code,
                        issue_action=error_contract.issue_action,
                    ).warning(
                        f"Unexpected issue_action "
                        f"'{error_contract.issue_action}' for "
                        f"{error_code}, treating as record_only"
                    )

            raise

    def execute_sync_request(
        self,
        request: ExecutionRequest,
        *,
        cwd: Path | None = None,
    ) -> CodeagentResult:
        """Execute a sync worker request through the unified execution shell."""
        from vibe3.agents.models import (
            ExecutionRole,
            create_codeagent_command,
        )

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
            tick_id=request.tick_id,
        )
        return self.execute_sync(command)
