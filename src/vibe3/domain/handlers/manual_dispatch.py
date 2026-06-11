"""Event handlers for CLI manual dispatch intents.

Handlers bridge CLI commands to the event bus. When a CLI command
(plan/run/review) is invoked, it publishes an intent event which
this handler receives and delegates to the appropriate execution function.

This unifies the CLI execution path with the heartbeat dispatch path,
enabling on_publish hooks and the rule engine to observe all executions.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from loguru import logger

from vibe3.domain.handler_registry import register_handler
from vibe3.models import (
    ManualPlanIntent,
    ManualReviewIntent,
    ManualRunIntent,
    ReviewRequest,
)

# Result sink for CLI commands that need return values (review verdict).
# Handler stores result after execution; CLI reads via get_pending_result().
_pending_results: dict[str, Any] = {}


def get_pending_result(key: str) -> Any | None:
    """Retrieve and clear a pending result stored by a handler."""
    return _pending_results.pop(key, None)


def _store_pending_error(key: str, exc: Exception) -> None:
    """Store a handler error for the originating CLI command to report."""
    _pending_results[key] = exc


@register_handler("ManualPlanIntent")
def handle_manual_plan_intent(event: ManualPlanIntent, /) -> None:
    """Handle ManualPlanIntent event by delegating to execute_spec_plan functions.

    The handler calls the same execution functions the CLI currently calls,
    ensuring that on_publish hooks and the rule engine observe all executions.
    """
    from vibe3.config import load_config_for_role
    from vibe3.roles import (
        execute_spec_plan_async,
        execute_spec_plan_sync,
    )

    logger.bind(
        domain="manual_plan_handler",
        issue_number=event.issue_number,
        branch=event.branch,
    ).info("Manual plan intent received")

    # Load config (handler needs its own config instance)
    try:
        config = load_config_for_role("plan", event.agent, event.backend, event.model)
    except Exception as e:
        logger.error(f"Config load failed for plan: {e}")
        _store_pending_error("plan", e)
        return

    # Use request already resolved by CLI (avoids duplicate spec resolution)
    request = event.request
    if request is None:
        error = ValueError("ManualPlanIntent missing request")
        logger.error(str(error))
        _store_pending_error("plan", error)
        return

    try:
        # Dispatch to sync or async execution
        if event.dry_run:
            # Dry-run mode: always sync, with dry_run=True
            execute_spec_plan_sync(
                request=request,  # type: ignore[arg-type]
                issue_number=event.issue_number,
                branch=event.branch,
                agent=event.agent,
                backend=event.backend,
                model=event.model,
                fresh_session=event.fresh_session,
                config=config,
                dry_run=True,
                show_prompt=event.show_prompt,
            )
        elif event.no_async:
            # Sync mode
            execute_spec_plan_sync(
                request=request,  # type: ignore[arg-type]
                issue_number=event.issue_number,
                branch=event.branch,
                agent=event.agent,
                backend=event.backend,
                model=event.model,
                fresh_session=event.fresh_session,
                config=config,
                dry_run=False,
                show_prompt=event.show_prompt,
            )
        else:
            # Async mode: construct cli_args from individual fields
            from vibe3.config import RoleCliOverrides

            overrides = RoleCliOverrides(
                agent=event.agent,
                backend=event.backend,
                model=event.model,
                fresh_session=event.fresh_session,
            )
            cli_args = ["plan"] + overrides.to_argv()

            result = execute_spec_plan_async(
                request=request,  # type: ignore[arg-type]
                issue_number=event.issue_number,
                branch=event.branch,
                cli_args=cli_args,
                agent=event.agent,
                backend=event.backend,
                model=event.model,
                fresh_session=event.fresh_session,
                config=config,
            )
            # Echo tmux info (same as CLI did)
            import typer

            typer.echo(f"tmux session: {result.tmux_session}")
            typer.echo(f"log: {result.log_path}")
    except Exception as e:
        logger.exception(f"Manual plan execution failed: {e}")
        _store_pending_error("plan", e)


@register_handler("ManualRunIntent")
def handle_manual_run_intent(event: ManualRunIntent, /) -> None:
    """Handle ManualRunIntent event by delegating to execute_manual_run.

    Reconstructs SimpleNamespace from flattened summary_* fields
    to match execute_manual_run's expected signature.
    """
    from vibe3.config import load_config_for_role
    from vibe3.roles import execute_manual_run

    logger.bind(
        domain="manual_run_handler",
        issue_number=event.issue_number,
        branch=event.branch,
    ).info("Manual run intent received")

    # Load config (same as CLI does)
    try:
        config = load_config_for_role("run", event.agent, event.backend, event.model)
    except Exception as e:
        logger.error(f"Config load failed for run: {e}")
        _store_pending_error("run", e)
        return

    # Reconstruct SimpleNamespace from flattened fields
    summary = SimpleNamespace(
        mode=event.summary_mode,
        plan_file=event.plan_file,
        message=event.summary_message,
        branch=event.summary_branch,
        worktree_root=None,  # Always None in CLI path
    )

    try:
        # Delegate to execute_manual_run
        execute_manual_run(
            config=config,
            branch=event.branch,
            issue_number=event.issue_number,
            instructions=event.instructions,
            plan_file=event.plan_file,
            skill=event.skill,
            summary=summary,
            dry_run=event.dry_run,
            no_async=event.no_async,
            show_prompt=event.show_prompt,
            agent=event.agent,
            backend=event.backend,
            model=event.model,
            fresh_session=event.fresh_session,
            publish=event.publish,
        )
    except Exception as e:
        logger.exception(f"Manual run execution failed: {e}")
        _store_pending_error("run", e)


@register_handler("ManualReviewIntent")
def handle_manual_review_intent(event: ManualReviewIntent, /) -> None:
    """Handle ManualReviewIntent event by delegating to review execution functions.

    For base review (is_base_review=True): calls execute_manual_review_sync/async.
    For branch review: calls run_issue_role_sync/async.

    Stores result in _pending_results for CLI to retrieve verdict.
    """
    from vibe3.config import load_config_for_role
    from vibe3.execution import (
        run_issue_role_async,
        run_issue_role_sync,
    )
    from vibe3.roles import (
        REVIEW_SYNC_SPEC,
        ReviewRunResult,
        execute_manual_review_async,
        execute_manual_review_sync,
    )

    logger.bind(
        domain="manual_review_handler",
        issue_number=event.issue_number,
        branch=event.branch,
        is_base_review=event.is_base_review,
    ).info("Manual review intent received")

    # Load config (same as CLI does)
    try:
        config = load_config_for_role("review", event.agent, event.backend, event.model)
    except Exception as e:
        logger.error(f"Config load failed for review: {e}")
        if event.no_async or event.dry_run:
            _pending_results["review"] = ReviewRunResult(
                "ERROR", None, event.issue_number
            )
        return

    if event.is_base_review:
        # Base review path
        # Type assertion: event.request is ReviewRequest for base reviews
        request = event.request if isinstance(event.request, ReviewRequest) else None
        if request is None:
            logger.error("ManualReviewIntent missing ReviewRequest for base review")
            if event.no_async or event.dry_run:
                _pending_results["review"] = ReviewRunResult(
                    "ERROR", None, event.issue_number
                )
            return

        if event.no_async or event.dry_run:
            # Sync mode (dry-run always sync)
            try:
                result = execute_manual_review_sync(
                    request=request,
                    dry_run=event.dry_run,
                    instructions=event.instructions,
                    issue_number=event.issue_number,
                    pr_number=None,
                    branch=event.branch,
                    agent=event.agent,
                    backend=event.backend,
                    model=event.model,
                    fresh_session=event.fresh_session,
                    config=config,
                    show_prompt=event.show_prompt,
                )
            except Exception:
                logger.exception("Review execution failed")
                result = ReviewRunResult("ERROR", None, event.issue_number)
            # Store result for CLI to retrieve
            _pending_results["review"] = result
        else:
            # Async mode
            result = execute_manual_review_async(
                request=request,
                instructions=event.instructions,
                issue_number=event.issue_number,
                pr_number=None,
                branch=event.branch,
                agent=event.agent,
                backend=event.backend,
                model=event.model,
                fresh_session=event.fresh_session,
            )
            # Echo tmux info (same as CLI did)
            import typer

            if result.tmux_session:
                typer.echo(f"tmux session: {result.tmux_session}")
            if result.log_path:
                typer.echo(f"log: {result.log_path}")
            # Don't store result for async mode (CLI won't read it)
    else:
        # Branch review path (run_issue_role)
        # Validate issue_number is present for branch review
        if event.issue_number is None:
            logger.error("ManualReviewIntent missing issue_number for branch review")
            return

        if event.no_async or event.dry_run:
            # Sync mode (run_issue_role_sync returns None)
            run_issue_role_sync(
                issue_number=event.issue_number,
                dry_run=event.dry_run,
                fresh_session=event.fresh_session,
                show_prompt=event.show_prompt,
                spec=REVIEW_SYNC_SPEC,
                branch=event.branch,
                agent=event.agent,
                backend=event.backend,
                model=event.model,
            )
            # Store None to signal completion (no verdict for branch review)
            _pending_results["review"] = None
        else:
            # Async mode
            run_issue_role_async(
                issue_number=event.issue_number,
                dry_run=event.dry_run,
                spec=REVIEW_SYNC_SPEC,
                branch=event.branch,
                agent=event.agent,
                backend=event.backend,
                model=event.model,
                fresh_session=event.fresh_session,
            )
            # Async mode doesn't store result
