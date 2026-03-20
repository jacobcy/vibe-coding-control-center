"""Review gate command - Pre-push review gate for CI/hooks.

This is an INTERNAL entry point for hooks and CI pipelines.
It is NOT exposed as a public CLI command.

Usage:
    # Internal entry (for hooks/CI):
    python -m vibe3.commands.review_gate --check-block

    # Direct import (for testing):
    from vibe3.commands.review_gate import run_review_gate
    run_review_gate(check_block=False)

Exit codes:
    0: Pass (low risk or review passed)
    1: Block (high risk with BLOCK verdict)
    2: Error (inspect/review execution failed)
"""

from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.review_helpers import run_inspect_json
from vibe3.config.settings import VibeConfig
from vibe3.models.review import ReviewRequest, ReviewScope
from vibe3.services.context_builder import build_review_context
from vibe3.services.review_parser import parse_codex_review
from vibe3.services.review_runner import ReviewAgentOptions, run_review_agent


def run_review_gate(check_block: bool = False) -> None:
    """Run the review gate.

    This is the core function that can be called directly or via CLI.

    Args:
        check_block: If True, return non-zero exit code on BLOCK verdict.

    Raises:
        typer.Exit: With appropriate exit code based on result.
    """
    log = logger.bind(domain="review_gate", action="check")
    log.info("Running review gate")

    # Load config
    config = VibeConfig.get_defaults()

    # 1. Run inspect to get risk level
    try:
        inspect_data: dict = run_inspect_json(["base", "origin/main"])
    except Exception as e:
        log.bind(error=str(e)).error("Inspect failed")
        typer.echo(f"ERROR: Inspect failed - {e}", err=True)
        raise typer.Exit(2)

    # Extract risk level
    score_data = inspect_data.get("score", {})
    risk_level = score_data.get("level") or score_data.get("risk_level", "LOW")
    risk_score = score_data.get("score", 0)

    log.bind(risk_level=risk_level, risk_score=risk_score).info(
        "Risk assessment complete"
    )
    typer.echo(f"Risk level: {risk_level} (score: {risk_score}/10)")

    # 2. Check if review is needed
    if risk_level not in ("HIGH", "CRITICAL"):
        log.info("Low risk - review gate passed")
        typer.echo("OK: Low risk, no review needed")
        return

    # 3. HIGH/CRITICAL risk - trigger review
    typer.echo(f"\nWARNING: {risk_level} risk detected!")
    typer.echo("Running local review before push...\n")

    try:
        # Build review request
        scope = ReviewScope.for_base("origin/main")
        changed_symbols_raw = inspect_data.get("changed_symbols", {})
        changed_symbols: dict[str, list[str]] | None = (
            changed_symbols_raw if changed_symbols_raw else None
        )

        request = ReviewRequest(scope=scope, changed_symbols=changed_symbols)
        prompt_content = build_review_context(request, config)

        # Run review agent
        options = ReviewAgentOptions(
            agent=config.review.agent_config.agent,
            backend=config.review.agent_config.backend,
            model=config.review.agent_config.model,
        )
        result = run_review_agent(prompt_content, options, task=None, dry_run=False)

        # Parse verdict
        review = parse_codex_review(result.stdout)

        typer.echo(result.stdout)
        typer.echo(
            f"\n=== Verdict: {review.verdict} | Comments: {len(review.comments)} ==="
        )

        # 4. Handle verdict based on risk level
        if review.verdict == "BLOCK":
            typer.echo(
                "\nERROR: Review verdict is BLOCK - fix issues before push", err=True
            )
            raise typer.Exit(1)

        if risk_level == "CRITICAL":
            # CRITICAL + non-zero exit = block
            if result.exit_code != 0:
                typer.echo(
                    "\nERROR: CRITICAL risk requires passing review before push",
                    err=True,
                )
                raise typer.Exit(1)

        # HIGH + review passed (or MAJOR) = allow push
        log.info("Review gate passed")
        typer.echo("\nOK: Review gate passed")

    except typer.Exit:
        # Re-raise typer.Exit (don't catch our own exit codes)
        raise
    except Exception as e:
        # Catch all other exceptions
        log.bind(error=str(e)).error("Review failed")

        if risk_level == "CRITICAL":
            typer.echo(
                f"ERROR: Review failed with CRITICAL risk - {e}",
                err=True,
            )
            raise typer.Exit(1)

        # HIGH risk: warn but allow push
        typer.echo(
            f"\nWARNING: Review failed but HIGH risk allows push - {e}",
            err=True,
        )


# -- CLI entry point for python -m vibe3.commands.review_gate --
_CHECK_BLOCK_OPT = Annotated[
    bool,
    typer.Option("--check-block", help="Return non-zero exit code on BLOCK verdict"),
]

_app = typer.Typer(
    name="review-gate",
    help="Pre-push review gate: check risk and optionally run review (internal)",
    add_completion=False,
    no_args_is_help=False,
)


@_app.callback(invoke_without_command=True)
def _cli_entry(
    ctx: typer.Context,
    check_block: _CHECK_BLOCK_OPT = False,
) -> None:
    """CLI entry point for python -m vibe3.commands.review_gate."""
    run_review_gate(check_block=check_block)


def run() -> None:
    """Entry point for python -m vibe3.commands.review_gate."""
    _app()


if __name__ == "__main__":
    run()
