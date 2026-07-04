"""Handoff write commands - Modify handoff state and record events."""

from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.common import enable_method_trace
from vibe3.models import VerdictValue
from vibe3.services.flow import resolve_branch_arg
from vibe3.services.handoff import HandoffService
from vibe3.services.pr import VerdictService
from vibe3.ui import console


def _record_handoff_reference(
    *,
    command: str,
    ref_label: str,
    ref_value: str,
    actor: str | None,
    trace: bool,
    method_name: str,
    branch: str | None = None,
    **extra_kw: object,
) -> None:
    if trace:
        enable_method_trace()

    specific_ref_key = f"{ref_label.lower()}_ref"
    logger.bind(
        command=command,
        actor=actor,
        ref=ref_value,
        branch=branch,
        **{specific_ref_key: ref_value},
    ).info(f"Recording {ref_label} handoff")

    service = HandoffService()
    method = getattr(service, method_name)
    # Support optional 'action' kwarg for indicate command
    # Branch is resolved to non-None string at command level
    extra_kwargs = {k: v for k, v in extra_kw.items() if v is not None}
    extra_kwargs["branch"] = branch
    method(ref_value, actor, **extra_kwargs)
    console.print(f"[green]✓[/] {ref_label} handoff recorded: {ref_value}")


def init(
    force: Annotated[bool, typer.Option("--yes", "-y", help="Force overwrite")] = False,
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name or issue number"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
    _quiet: bool = False,  # Internal use: suppress output
) -> None:
    """Initialize handoff file with issue context for a branch.

    Fetches issue comments via TaskShowService and populates handoff with context.
    Called by:
    - vibe3 internal bootstrap (auto)
    - vibe3 handoff init (manual)
    """
    if trace:
        enable_method_trace()

    target_branch = resolve_branch_arg(branch)

    logger.bind(command="handoff init", force=force, branch=target_branch).info(
        "Initializing handoff"
    )

    from vibe3.clients import GitClient, GitHubClient, SQLiteClient
    from vibe3.services.flow import FlowService

    store = SQLiteClient()
    git = GitClient()
    github = GitHubClient()
    flow_service = FlowService(store=store, git_client=git)

    # Ensure flow exists for standalone `vibe3 handoff init` usage.
    # When called via ensure_current_handoff_for_flow (flow update / bootstrap),
    # the caller has already ensured the flow — this is a cheap idempotent check.
    flow_service.ensure_flow_for_branch(branch=target_branch, source="handoff_init")

    service = HandoffService()
    handoff_path = service.storage.ensure_current_handoff(
        force=force, branch=target_branch
    )

    # Populate with issue context if branch has bound issue
    from vibe3.services.issue import IssueFlowService
    from vibe3.services.task import TaskShowService

    issue_flow_service = IssueFlowService(store=store)

    # Resolve issue number from branch
    issue_number = issue_flow_service.resolve_task_issue_number(target_branch)

    if issue_number:
        try:
            task_show = TaskShowService(
                store=store,
                flow_service=flow_service,
                github_client=github,
                git_client=git,
            )

            issue_data = task_show.fetch_issue_with_comments(issue_number)
            if isinstance(issue_data, dict):
                # 1. Append issue summary
                issue_title = issue_data.get("title", "N/A")
                issue_state = issue_data.get("state", "N/A")
                issue_summary = (
                    f"Issue #{issue_number}: {issue_title}\n" f"State: {issue_state}"
                )
                service.append_current_handoff(
                    message=issue_summary,
                    actor="init",
                    kind="context",
                    branch=target_branch,
                )

                # 2. Extract human comments
                comments_raw = issue_data.get("comments", [])
                comments = comments_raw if isinstance(comments_raw, list) else []

                from vibe3.services.shared import is_human_comment

                # Find latest human instruction
                latest_human_comment = None
                for comment in reversed(comments):
                    if is_human_comment(comment):
                        latest_human_comment = comment
                        break

                if latest_human_comment:
                    comment_summary = task_show.build_comment_summary(
                        latest_human_comment, full_body=True
                    )
                    if comment_summary:
                        human_msg = (
                            f"Latest human instruction by {comment_summary.author}:\n"
                            f"{comment_summary.body}"
                        )
                        service.append_current_handoff(
                            message=human_msg,
                            actor="init",
                            kind="context",
                            branch=target_branch,
                        )

                # 3. Append latest comment if different from human instruction
                if comments and comments[-1] != latest_human_comment:
                    latest_comment_summary = task_show.build_comment_summary(
                        comments[-1], full_body=True
                    )
                    if latest_comment_summary:
                        latest_msg = (
                            f"Latest comment by {latest_comment_summary.author}:\n"
                            f"{latest_comment_summary.body}"
                        )
                        service.append_current_handoff(
                            message=latest_msg,
                            actor="init",
                            kind="context",
                            branch=target_branch,
                        )

                # 4. Append PR CI status if available
                from vibe3.services.pr import PRService

                pr_service = PRService()
                pr_status = pr_service.get_branch_pr_status(target_branch)

                if pr_status:
                    pr_number = pr_status.number
                    ci_status = pr_status.ci_status or "unknown"
                    pr_msg = f"PR #{pr_number}: CI status: {ci_status}"
                    service.append_current_handoff(
                        message=pr_msg,
                        actor="init",
                        kind="ci_status",
                        branch=target_branch,
                    )
        except Exception as e:
            # Non-critical failure: log and continue
            logger.bind(
                command="handoff init", issue=issue_number, branch=target_branch
            ).warning(f"Failed to fetch issue context: {e}")

    if not _quiet:
        console.print(f"[green]✓[/] Handoff file ready: {handoff_path}")


def append(
    message: Annotated[str, typer.Argument(help="Message to append")],
    actor: Annotated[
        str | None,
        typer.Option(
            "--actor",
            "-a",
            help=(
                "Actor identifier (format: backend/model, e.g., codex/gpt-5.4). "
                "Default: flow actor if configured, otherwise workflow."
            ),
        ),
    ] = None,
    kind: Annotated[
        str,
        typer.Option("--kind", "-k", help="Update kind (finding/blocker/next/note)"),
    ] = "note",
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name or issue number"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
) -> None:
    """Append lightweight update to handoff file for a branch."""
    if trace:
        enable_method_trace()

    target_branch = resolve_branch_arg(branch)

    logger.bind(
        command="handoff append", actor=actor, kind=kind, branch=target_branch
    ).info("Appending handoff update")

    service = HandoffService()
    handoff_path = service.append_current_handoff(
        message, actor, kind, branch=target_branch
    )

    console.print("[green]✓[/] Appended handoff update")
    console.print(f"  [dim]File: {handoff_path}[/]")


def plan(
    plan_ref: Annotated[str, typer.Argument(help="Plan document reference")],
    actor: Annotated[
        str | None,
        typer.Option(
            "--actor",
            "-a",
            help=(
                "Actor identifier (format: backend/model, e.g., codex/gpt-5.4). "
                "Default: flow actor if configured, otherwise workflow."
            ),
        ),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name or issue number"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
) -> None:
    """Record plan handoff for a branch."""

    target_branch = resolve_branch_arg(branch)

    _record_handoff_reference(
        command="handoff plan",
        ref_label="Plan",
        ref_value=plan_ref,
        actor=actor,
        trace=trace,
        method_name="record_plan",
        branch=target_branch,
    )


def spec(
    spec_ref: Annotated[str, typer.Argument(help="Canonical spec document reference")],
    actor: Annotated[
        str | None,
        typer.Option(
            "--actor",
            "-a",
            help=(
                "Actor identifier (format: backend/model, e.g., codex/gpt-5.4). "
                "Default: flow actor if configured, otherwise workflow."
            ),
        ),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name or issue number"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
) -> None:
    """Record canonical spec handoff for a branch.

    The spec_ref MUST be a canonical repository-relative path of the form
    ``.specify/specs/<NNN-slug>/spec.md`` (ADR-0006). Legacy issue-ids
    (``#nnn``) are rejected on write; read-side compatibility is preserved.
    """

    target_branch = resolve_branch_arg(branch)

    _record_handoff_reference(
        command="handoff spec",
        ref_label="Spec",
        ref_value=spec_ref,
        actor=actor,
        trace=trace,
        method_name="record_spec",
        branch=target_branch,
    )


def report(
    report_ref: Annotated[str, typer.Argument(help="Report document reference")],
    actor: Annotated[
        str | None,
        typer.Option(
            "--actor",
            "-a",
            help=(
                "Actor identifier (format: backend/model, e.g., codex/gpt-5.4). "
                "Default: flow actor if configured, otherwise workflow."
            ),
        ),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name or issue number"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
) -> None:
    """Record report handoff for a branch."""

    target_branch = resolve_branch_arg(branch)

    _record_handoff_reference(
        command="handoff report",
        ref_label="Report",
        ref_value=report_ref,
        actor=actor,
        trace=trace,
        method_name="record_report",
        branch=target_branch,
    )


def indicate(
    indicate_ref: Annotated[
        str, typer.Argument(help="Manager indicate document reference")
    ],
    actor: Annotated[
        str | None,
        typer.Option(
            "--actor",
            "-a",
            help=(
                "Actor identifier (format: backend/model, "
                "e.g., gemini/gemini-3-flash-preview). "
                "Default: flow actor if configured, otherwise workflow."
            ),
        ),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name or issue number"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
) -> None:
    """Record manager indicate handoff for a branch.

    Manager directive to downstream agents.
    Provide a structured handoff file reference for downstream agent context.
    """

    target_branch = resolve_branch_arg(branch)

    _record_handoff_reference(
        command="handoff indicate",
        ref_label="Indicate",
        ref_value=indicate_ref,
        actor=actor,
        trace=trace,
        method_name="record_indicate",
        branch=target_branch,
    )


def audit(
    audit_ref: Annotated[str, typer.Argument(help="Audit document reference")],
    actor: Annotated[
        str | None,
        typer.Option(
            "--actor",
            "-a",
            help=(
                "Actor identifier (format: backend/model, e.g., codex/gpt-5.4). "
                "Default: flow actor if configured, otherwise workflow."
            ),
        ),
    ] = None,
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name or issue number"),
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
) -> None:
    """Record audit handoff for a branch."""

    target_branch = resolve_branch_arg(branch)

    _record_handoff_reference(
        command="handoff audit",
        ref_label="Audit",
        ref_value=audit_ref,
        actor=actor,
        trace=trace,
        method_name="record_audit",
        branch=target_branch,
    )


def next_step(
    message: Annotated[str, typer.Argument(help="Next step text")],
    branch: Annotated[
        str | None,
        typer.Option("--branch", "-b", help="Branch name or issue number"),
    ] = None,
    actor: Annotated[str | None, typer.Option("--actor", "-a")] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
) -> None:
    """Write next step to flow state for a target branch."""
    if trace:
        enable_method_trace()

    target_branch = resolve_branch_arg(branch)
    service = HandoffService()

    # Validate flow exists before writing next_step
    flow_state = service.store.get_flow_state(target_branch)
    if not flow_state:
        typer.echo(
            f"Error: 目标分支 '{target_branch}' 没有 flow\n"
            "先执行 `vibe3 flow add <name>` 或切到已有 flow 的分支",
            err=True,
        )
        raise typer.Exit(1)

    service.record_next_step(target_branch, message, actor)
    console.print(f"[green]✓[/] Next step updated: {message}")


def verdict(
    verdict_value: Annotated[
        VerdictValue,
        typer.Argument(
            help="Verdict value (PASS, MINOR, MAJOR, BLOCK, REFUSE, UNKNOWN)"
        ),
    ],
    reason: Annotated[
        str | None, typer.Option("--reason", "-r", help="Verdict reason")
    ] = None,
    issues: Annotated[
        str | None, typer.Option("--issues", "-i", help="Issues description")
    ] = None,
    branch: Annotated[
        str | None, typer.Argument(help="Target branch (current if not specified)")
    ] = None,
    trace: Annotated[
        bool, typer.Option("--trace", help="启用调用链路追踪（set VIBE3_TRACE=1）")
    ] = False,
) -> None:
    """Write verdict to handoff chain and flow state.

    This command records an agent's judgment about the flow state.
    It does NOT make any decisions - it only records the verdict.

    Verdict values:
    - PASS: No issues, ready to merge
    - MINOR: Minor issues, merge acceptable with follow-up
    - MAJOR: Issues found, needs fix before merge
    - BLOCK: Critical issues, blocks merge
    - REFUSE: Cannot perform normal review (ethical/legal concerns)
    - UNKNOWN: Cannot determine

    Examples:
        vibe3 handoff verdict MAJOR --reason "Found indentation errors and missing docs"
        vibe3 handoff verdict PASS --reason "Code looks good"
        vibe3 handoff verdict BLOCK --reason "Security vulnerability found"
    """
    if trace:
        enable_method_trace()

    target_branch = resolve_branch_arg(branch)

    logger.bind(
        command="handoff verdict",
        verdict=verdict_value,
        reason=reason,
        branch=target_branch,
    ).info("Writing verdict")

    service = VerdictService()
    record = service.write_verdict(
        verdict=verdict_value,
        reason=reason,
        issues=issues,
        branch=target_branch,
    )

    console.print(f"[green]✓[/] Verdict written: {verdict_value}")
    if reason:
        console.print(f"  [dim]Reason: {reason}[/]")
    console.print(f"  [dim]Actor: {record.actor}[/]")
    console.print(f"  [dim]Role: {record.role}[/]")


def register_write_commands(app: typer.Typer) -> None:
    """Register write handoff commands."""
    app.command()(init)
    app.command()(append)
    app.command()(plan)
    app.command()(spec)
    app.command()(report)
    app.command()(indicate)
    app.command()(audit)
    app.command("next")(next_step)
    app.command()(verdict)
