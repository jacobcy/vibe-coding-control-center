"""Event handlers for CLI manual dispatch intents.

Handlers bridge CLI commands to the event bus. When a CLI command
(plan/run/review) is invoked, it publishes an intent event which
this handler receives and delegates to the appropriate execution function.

This unifies the CLI execution path with the heartbeat dispatch path,
enabling on_publish hooks and the rule engine to observe all executions.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.config import resolve_effective_agent_options
from vibe3.domain.handler_registry import register_handler
from vibe3.models import (
    ManualPlanIntent,
    ManualReviewIntent,
    ManualRunIntent,
    ReviewRequest,
)
from vibe3.services.shared import log_dispatch_error

if TYPE_CHECKING:
    from vibe3.agents import CodeagentResult
    from vibe3.roles import ReviewRunResult

# Result sink for CLI commands that need return values (review verdict).
# Handler stores result after execution; CLI reads via get_pending_result().
_pending_results: dict[str, Any] = {}


def get_pending_result(key: str) -> Any | None:
    """Retrieve and clear a pending result stored by a handler."""
    return _pending_results.pop(key, None)


@register_handler("ManualPlanIntent")
def handle_manual_plan_intent(event: ManualPlanIntent, /) -> CodeagentResult | None:
    """Handle ManualPlanIntent event by delegating to execute_spec_plan functions.

    The handler calls the same execution functions the CLI currently calls,
    ensuring that on_publish hooks and the rule engine observe all executions.

    Returns:
        CodeagentResult on success or error, None if config load failed.
    """
    from vibe3.agents import CodeagentResult
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
        return CodeagentResult(success=False, stderr=f"Config load failed: {e}")

    # Use request already resolved by CLI (avoids duplicate spec resolution)
    request = event.request
    if request is None:
        error_msg = "ManualPlanIntent missing request"
        logger.error(error_msg)
        return CodeagentResult(success=False, stderr=error_msg)

    try:
        # Dispatch to sync or async execution
        if event.dry_run:
            # Dry-run mode: always sync, with dry_run=True
            return execute_spec_plan_sync(
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
            return execute_spec_plan_sync(
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

            return execute_spec_plan_async(
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
    except Exception as e:
        log_dispatch_error("Manual plan dispatch failed", e)
        return CodeagentResult(success=False, stderr=f"Dispatch failed: {e}")


@register_handler("ManualRunIntent")
def handle_manual_run_intent(event: ManualRunIntent, /) -> CodeagentResult | None:
    """Handle ManualRunIntent event by delegating to execute_manual_run.

    Reconstructs SimpleNamespace from flattened summary_* fields
    to match execute_manual_run's expected signature.

    Returns:
        CodeagentResult from execution, or None on config load failure.
    """
    from vibe3.agents import CodeagentResult
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
        return CodeagentResult(success=False, stderr=f"Config load failed: {e}")

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
        return execute_manual_run(
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
        log_dispatch_error("Manual run dispatch failed", e)
        return CodeagentResult(success=False, stderr=f"Dispatch failed: {e}")


@register_handler("ManualReviewIntent")
def handle_manual_review_intent(event: ManualReviewIntent, /) -> ReviewRunResult | None:
    """Handle ManualReviewIntent event by delegating to review execution functions.

    For base review (is_base_review=True): calls execute_manual_review_sync/async.
    For branch review: calls run_issue_role_sync/async.

    Stores result in _pending_results for CLI to retrieve verdict (backward compat).
    Also returns result for publish_and_wait pattern.

    Returns:
        ReviewRunResult for base review or branch review sync, None for async or errors.
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
            error_result = ReviewRunResult("ERROR", None, event.issue_number)
            _pending_results["review"] = error_result
            return error_result
        return None

    if event.is_base_review:
        # Base review path
        # Type assertion: event.request is ReviewRequest for base reviews
        request = event.request if isinstance(event.request, ReviewRequest) else None
        if request is None:
            logger.error("ManualReviewIntent missing ReviewRequest for base review")
            if event.no_async or event.dry_run:
                error_result = ReviewRunResult("ERROR", None, event.issue_number)
                _pending_results["review"] = error_result
                return error_result
            return None

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
            except Exception as e:
                log_dispatch_error("Review dispatch failed", e)
                result = ReviewRunResult("ERROR", None, event.issue_number)
            # Store result for CLI to retrieve (backward compat)
            _pending_results["review"] = result
            return result
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
            return result
    else:
        # Branch review path (run_issue_role)
        # Validate issue_number is present for branch review
        if event.issue_number is None:
            logger.error("ManualReviewIntent missing issue_number for branch review")
            return None

        if event.no_async or event.dry_run:
            # Resolve effective options once; pass resolved backend/model
            # to run_issue_role_sync so its internal resolution is a no-op.
            from vibe3.execution import resolve_command_agent_options

            options = resolve_command_agent_options(
                config=config,
                section="review",
                agent=event.agent,
                backend=event.backend,
                model=event.model,
            )
            effective = resolve_effective_agent_options(options)

            # Sync mode
            run_issue_role_sync(
                issue_number=event.issue_number,
                dry_run=event.dry_run,
                fresh_session=event.fresh_session,
                show_prompt=event.show_prompt,
                spec=REVIEW_SYNC_SPEC,
                branch=event.branch,
                agent=event.agent,
                backend=effective.backend or event.backend,
                model=effective.model or event.model,
            )
            verdict = "DRY_RUN" if event.dry_run else "OK"
            result = ReviewRunResult(
                verdict,
                None,
                event.issue_number,
                backend=effective.backend,
                model=effective.model,
            )
            # Store for backward compat
            _pending_results["review"] = result
            return result
        else:
            # Async mode
            launch = run_issue_role_async(
                issue_number=event.issue_number,
                dry_run=event.dry_run,
                spec=REVIEW_SYNC_SPEC,
                branch=event.branch,
                agent=event.agent,
                backend=event.backend,
                model=event.model,
                fresh_session=event.fresh_session,
            )
            resolved_backend = launch.backend if launch else None
            resolved_model = launch.model if launch else None
            if not resolved_backend or not resolved_model:
                from vibe3.execution import resolve_command_agent_options

                options = resolve_command_agent_options(
                    config=config,
                    section="review",
                    agent=event.agent,
                    backend=event.backend,
                    model=event.model,
                )
                effective = resolve_effective_agent_options(options)
                resolved_backend = resolved_backend or effective.backend
                resolved_model = resolved_model or effective.model
            return ReviewRunResult(
                "ASYNC" if launch is None or launch.launched else "ERROR",
                None,
                event.issue_number,
                tmux_session=launch.tmux_session if launch else None,
                log_path=launch.log_path if launch else None,
                backend=resolved_backend,
                model=resolved_model,
            )
