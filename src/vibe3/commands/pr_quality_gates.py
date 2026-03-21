"""Quality gates for PR lifecycle commands."""

from __future__ import annotations

from rich.console import Console
from typer import Exit


def _render_score_explanation(console: Console, score: dict[str, object]) -> None:
    """Render explainable risk details."""
    reason = score.get("reason")
    if isinstance(reason, str) and reason:
        console.print(f"[yellow]原因[/]: {reason}")

    trigger_factors = score.get("trigger_factors")
    if isinstance(trigger_factors, list) and trigger_factors:
        console.print("[yellow]扣分项[/]:")
        for factor in trigger_factors:
            console.print(f"  - {factor}")

    recommendations = score.get("recommendations")
    if isinstance(recommendations, list) and recommendations:
        console.print("[yellow]建议[/]:")
        for item in recommendations:
            console.print(f"  - {item}")


def run_coverage_gate(console: Console, yes: bool = False) -> None:
    """Run coverage quality gate.

    Args:
        console: Rich console for output
        yes: Bypass coverage check

    Raises:
        Exit: If coverage gate fails
        Exception: If coverage check fails (fail-fast, no interactive bypass)
    """
    if yes:
        console.print("\n[yellow]⚠️  Skipping coverage gate (--yes)[/]")
        return

    from vibe3.services.coverage_service import CoverageService

    console.print("\n[cyan]Running coverage check...[/]")

    coverage_service = CoverageService()
    coverage = coverage_service.run_coverage_check()

    if not coverage.all_passing:
        console.print("\n[red]✗ Coverage gate failed[/]")
        overall = coverage.overall_percent
        console.print(f"[yellow]Overall coverage[/]: {overall:.1f}%")

        failing = coverage.get_failing_layers()
        for layer in failing:
            pct = layer.coverage_percent
            console.print(
                f"  [red]✗ {layer.layer_name}[/]: "
                f"{pct:.1f}% < {layer.threshold}% "
                f"(gap: {layer.gap:.1f}%)"
            )

        console.print("\n[dim]Increase coverage or use --yes to bypass[/]")
        raise Exit(1)

    # Display passed coverage
    console.print("\n[green]✓ Coverage gate passed[/]")
    overall = coverage.overall_percent
    console.print(f"[cyan]Overall[/]: {overall:.1f}%")
    svc_pct = coverage.services.coverage_percent
    cli_pct = coverage.clients.coverage_percent
    cmd_pct = coverage.commands.coverage_percent
    console.print(f"  [green]✓ services[/]: {svc_pct:.1f}%")
    console.print(f"  [green]✓ clients[/]: {cli_pct:.1f}%")
    console.print(f"  [green]✓ commands[/]: {cmd_pct:.1f}%")


def run_risk_gate(console: Console, pr_number: int) -> None:
    """Run risk score quality gate.

    Args:
        console: Rich console for output
        pr_number: PR number to check

    Raises:
        Exit: If risk gate fails
        Exception: If risk check fails (fail-fast, no interactive bypass)
    """
    from vibe3.commands.review_helpers import run_inspect_json

    # Call inspect pr to get risk score
    analysis = run_inspect_json(["pr", str(pr_number)])
    score_data = analysis.get("score", {})
    # Type assertion for score dict
    score = score_data if isinstance(score_data, dict) else {}

    # Check if blocked
    if score.get("block", False):
        console.print("\n[red]✗ 质量门禁失败[/]")
        console.print("[red]PR 被阻断：高风险变更[/]")
        console.print(
            "\n[yellow]风险评分[/]: "
            f"{score.get('score', 'N/A')} "
            f"({score.get('level', 'N/A')})"
        )
        _render_score_explanation(console, score)

        console.print("\n[dim]请修复问题或使用 --yes 跳过（不推荐）[/]")
        raise Exit(1)

    # Display passed info
    console.print("\n[green]✓ 质量门禁通过[/]")
    console.print(f"[cyan]风险等级[/]: {score.get('level', 'N/A')}")
    console.print(f"[cyan]风险评分[/]: {score.get('score', 'N/A')}")
    _render_score_explanation(console, score)
