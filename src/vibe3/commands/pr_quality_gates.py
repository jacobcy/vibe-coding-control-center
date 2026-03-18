"""Quality gates for PR lifecycle commands."""
from __future__ import annotations

from rich.console import Console
from typer import Exit


def run_coverage_gate(console: Console, skip_coverage: bool = False) -> None:
    """Run coverage quality gate.

    Args:
        console: Rich console for output
        skip_coverage: Skip coverage check

    Raises:
        Exit: If coverage gate fails
    """
    if skip_coverage:
        console.print("\n[yellow]⚠️  Skipping coverage gate (--skip-coverage)[/]")
        return

    try:
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

            console.print(
                "\n[dim]Increase coverage or use " "--skip-coverage to skip[/]"
            )
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

    except Exception as e:
        console.print("\n[yellow]⚠️  Warning: Coverage check failed[/]")
        console.print(f"[yellow]Error: {e}[/]")

        # Ask to continue
        from typer import confirm

        if not confirm("Continue without coverage check?"):
            raise Exit(1)


def run_risk_gate(console: Console, pr_number: int) -> None:
    """Run risk score quality gate.

    Args:
        console: Rich console for output
        pr_number: PR number to check

    Raises:
        Exit: If risk gate fails
    """
    try:
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
            console.print(f"[yellow]原因[/]: {score.get('reason', '未知')}")

            console.print("\n[dim]请修复问题或使用 --force 跳过（不推荐）[/]")
            raise Exit(1)

        # Display passed info
        console.print("\n[green]✓ 质量门禁通过[/]")
        console.print(f"[cyan]风险等级[/]: {score.get('level', 'N/A')}")
        console.print(f"[cyan]风险评分[/]: {score.get('score', 'N/A')}")

    except Exception as e:
        console.print("\n[yellow]⚠️  警告：质量门禁检查失败[/]")
        console.print(f"[yellow]错误：{e}[/]")

        # Ask to continue
        from typer import confirm

        if not confirm("是否在没有质量检查的情况下继续？"):
            raise Exit(1)
