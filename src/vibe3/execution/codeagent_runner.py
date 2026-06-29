"""Sync codeagent execution utilities for command-mode role entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

from loguru import logger
from typer import echo

from vibe3.clients import GitClient, SQLiteClient

if TYPE_CHECKING:
    from loguru import Logger

    from vibe3.agents import (
        CodeagentCommand,
        CodeagentResult,
    )
    from vibe3.exceptions import ErrorSeverity
    from vibe3.models import AgentResult
from vibe3.config import VibeConfig, get_role_section, resolve_effective_agent_options
from vibe3.execution.codeagent_support import resolve_command_agent_options
from vibe3.execution.execution_lifecycle import (
    execution_prefix,
    persist_execution_lifecycle_event,
)
from vibe3.execution.noop_gate import apply_unified_noop_gate
from vibe3.execution.session_service import load_session_id
from vibe3.models import AgentOptions, ExecutionRequest
from vibe3.services.handoff import HandoffService
from vibe3.services.shared import format_agent_actor


def _severity_event_type(role: str, severity: "ErrorSeverity") -> str:
    """Build event type suffix based on error severity."""
    from vibe3.exceptions import ErrorSeverity

    prefix = execution_prefix(role)  # type: ignore[arg-type]
    if severity == ErrorSeverity.WARNING:
        return f"codeagent_{prefix}_warning"
    elif severity == ErrorSeverity.CRITICAL:
        return f"codeagent_{prefix}_aborted"
    else:  # ERROR
        return f"codeagent_{prefix}_error"


def _format_agent_error_metadata(metadata: dict[str, str] | None) -> str:
    """Format agent error metadata for operator-visible diagnostics."""
    if not metadata:
        return ""
    return ", ".join(f"{key}={value}" for key, value in metadata.items())


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
        from vibe3.clients import GhIssueLabelPort
        from vibe3.config import get_handoff_state_label, load_orchestra_config

        config = load_orchestra_config()
        handoff_label = get_handoff_state_label(config.supervisor_handoff)

        try:
            repo = config.repo
            labels_client = GhIssueLabelPort(repo=repo)
            labels_client.remove_issue_label(issue_number, handoff_label)
            log.info(f"Removed {handoff_label} label from #{issue_number}")
        except Exception as exc:
            log.warning(
                f"Failed to remove {handoff_label} label from #{issue_number}: {exc}"
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
            fallback = Path.cwd()
            logger.bind(domain="codeagent").warning(
                f"Failed to resolve worktree root via git, "
                f"falling back to process cwd: {fallback}"
            )
            return fallback

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
                from vibe3.clients import GitHubClient

                # Only need labels and state for state label extraction
                issue_payload = GitHubClient().view_issue(
                    command.issue_number,
                    repo=getattr(self.config, "repo", None),
                    fields=["labels", "state"],
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

            # Reset AUP rejection counter on successful execution so that
            # intermittent AUP issues do not accumulate across recoveries.
            flow_state_for_reset = ctx.store.get_flow_state(ctx.branch) or {}
            if int(flow_state_for_reset.get("aup_rejection_count", 0) or 0) > 0:
                ctx.store.update_flow_state(
                    ctx.branch,
                    aup_rejection_count=0,
                    last_aup_rejection_at=None,
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
            # Only task/issue- branches participate in orchestra state machine;
            # human-managed branches (e.g. dev/issue-) skip the label transition check.
            _noop_gate_roles = {"manager", "planner", "executor", "reviewer"}
            if (
                command.issue_number is not None
                and command.role in _noop_gate_roles
                and ctx.branch.startswith("task/issue-")
            ):
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
        from vibe3.agents import CodeagentBackend, CodeagentResult

        log = logger.bind(
            domain="codeagent",
            role=command.role,
            handoff_kind=command.handoff_kind,
        )

        ctx = self._prepare_sync_context(command)
        log.info("Starting sync execution")
        prompt_content = command.context_builder()
        # Resolve preset once here; pass pre-resolved options to
        # CodeagentBackend.run() so its internal resolution is a no-op.
        effective = resolve_effective_agent_options(ctx.options)

        # Skip execution header in dry_run mode to avoid duplication
        # Backend.run() will print "=== Prompt Composition ===" header
        if not command.dry_run:
            echo(f"-> Executing with {effective.agent or effective.backend}...")
            if effective.model:
                echo(f"   model: {effective.model}")

        try:
            agent_result = CodeagentBackend().run(
                prompt=prompt_content,
                options=effective,
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
                    backend=effective.backend,
                    model=effective.model,
                    issue_number=command.issue_number,
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
                backend=effective.backend,
                model=effective.model,
                issue_number=command.issue_number,
            )
        except Exception as exc:
            from vibe3.exceptions import (
                AgentExecutionError,
                classify_error_hybrid,
                get_error_handling_contract,
            )

            # Classify error and record to SQLite for threshold tracking.
            # FailedGate.check() reads SQLite error_log on next heartbeat tick.
            error_code = classify_error_hybrid(exc)

            # Get handling contract for severity-aware behavior
            error_contract = get_error_handling_contract(error_code)

            # AUP rejection: record to error_log (WARNING severity, auto-inferred
            # from registry) for observability, increment counter, block at
            # threshold. No early raise — fall through to the common timeline
            # recording path below, then the final raise propagates.
            if error_code == "E_AUP_REJECTION" and ctx.branch and ctx.store:
                try:
                    from vibe3.services.orchestra import record_error

                    record_error(
                        error_code=error_code,
                        error_message=str(exc),
                        tick_id=command.tick_id,
                        issue_number=command.issue_number,
                        branch=ctx.branch,
                        store=ctx.store,
                    )
                except Exception as record_exc:
                    log.warning(
                        f"Failed to record AUP rejection to error_log: " f"{record_exc}"
                    )

                count = ctx.store.increment_aup_rejection(ctx.branch)
                max_retries = error_contract.max_retries or 3

                if count >= max_retries:
                    from vibe3.services.flow import BlockedStateService

                    reason = (
                        f"AUP rejection threshold reached "
                        f"({count}/{max_retries} attempts)"
                    )
                    try:
                        bss = BlockedStateService(store=ctx.store)
                        if command.issue_number is None:
                            raise SystemError(
                                f"AUP rejection: cannot block flow "
                                f"'{ctx.branch}' — no task issue linked. "
                                "Flow is in incomplete state."
                            )
                        bss.set_block(
                            issue_number=command.issue_number,
                            branch=ctx.branch,
                            reason=reason,
                            actor=ctx.actor,
                        )
                        log.error(f"AUP rejection blocked flow: {reason}")
                    except Exception as block_exc:
                        log.bind(
                            domain="codeagent",
                            role=command.role,
                            issue_number=command.issue_number,
                        ).error(
                            f"AUP block partially failed "
                            f"(DB cached, body/label may not be updated): "
                            f"{block_exc}"
                        )
                else:
                    log.warning(
                        f"AUP rejection #{count}/{max_retries} "
                        f"(will block at {max_retries})"
                    )

            agent_metadata = (
                exc.metadata if isinstance(exc, AgentExecutionError) else None
            )
            metadata_summary = _format_agent_error_metadata(agent_metadata)
            error_message = str(exc)
            if metadata_summary:
                error_message = (
                    f"{error_message}\n\n[agent metadata] {metadata_summary}"
                )

            # Build abort message
            abort_msg = (
                f"{command.role.capitalize()} aborted "
                f"(status: blocked, error: {error_code})"
            )

            # Record abort event to flow timeline
            if ctx.branch and ctx.store:
                abort_refs: dict[str, str] = {
                    "reason": error_message,
                    "error_code": error_code,
                    "status": "blocked",
                }
                if agent_metadata:
                    abort_refs.update(agent_metadata)
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
                    error_contract=error_contract,
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
                elif error_contract.issue_action == "block_after_retries":
                    logger.bind(
                        domain="codeagent",
                        role=command.role,
                        issue_number=command.issue_number,
                        error_code=error_code,
                        severity=error_contract.severity.value,
                    ).info(
                        f"AUP rejection recorded: {error_code} "
                        f"({error_contract.severity.value}) - "
                        "retry counter incremented, flow will block "
                        "after threshold"
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
        from vibe3.agents import (
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
