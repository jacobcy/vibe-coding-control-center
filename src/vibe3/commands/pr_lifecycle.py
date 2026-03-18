"""PR lifecycle commands (ready, merge)."""

import json
from typing import Annotated

import typer
from loguru import logger

from vibe3.commands.pr_helpers import noop_context
from vibe3.observability.logger import setup_logging
from vibe3.observability.trace import trace_context
from vibe3.services.pr_service import PRService
from vibe3.ui.pr_ui import render_pr_merged, render_pr_ready


def register_lifecycle_commands(app: typer.Typer) -> None:
    """Register pr lifecycle commands."""

    @app.command()
    def ready(
        pr_number: Annotated[int, typer.Argument(help="PR number")],
        yes: Annotated[
            bool, typer.Option("-y", "--yes", help="自动确认（跳过交互）")
        ] = False,  # noqa: E501
        force: Annotated[
            bool, typer.Option("--force", help="跳过质量门禁检查")
        ] = False,  # noqa: E501
        skip_coverage: Annotated[
            bool, typer.Option("--skip-coverage", help="跳过覆盖率检查")
        ] = False,  # noqa: E501
        trace: Annotated[
            bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="JSON 格式输出")
        ] = False,  # noqa: E501
        yaml_output: Annotated[
            bool, typer.Option("--yaml", help="YAML 格式输出")
        ] = False,  # noqa: E501
    ) -> None:
        """Mark PR as ready with quality gates.

        质量门禁检查:
        - 覆盖率检查（分层覆盖率统计）
        - 风险评分检查（来自 inspect pr）

        使用 --skip-coverage 跳过覆盖率检查.
        使用 --force 跳过所有检查（不推荐）.
        """
        if json_output and yaml_output:
            typer.echo("Error: Cannot use both --json and --yaml", err=True)
            raise typer.Exit(1)

        if trace:
            setup_logging(verbose=2)

        ctx = (
            trace_context(command="pr ready", domain="pr", pr_number=pr_number)
            if trace
            else noop_context()
        )
        with ctx:
            logger.bind(command="pr ready", pr_number=pr_number, force=force).info(
                "Marking PR as ready for review"
            )

            # 1. 质量门禁检查（除非 --force）
            if not force:
                from rich.console import Console

                from vibe3.commands.pr_quality_gates import (
                    run_coverage_gate,
                    run_risk_gate,
                )

                console = Console()

                # 1.1 覆盖率检查
                run_coverage_gate(console, skip_coverage)

                # 1.2 风险评分检查
                run_risk_gate(console, pr_number)

            else:
                from rich.console import Console

                console = Console()
                console.print("\n[yellow]⚠️  跳过质量门禁检查 (--force)[/]")

            # 2. 确认操作（除非 --yes）
            if not yes:
                confirmed = typer.confirm(
                    "Mark PR #"
                    f"{pr_number} as ready for review? (draft → ready, irreversible)"
                )
                if not confirmed:
                    logger.info("Aborted by user")
                    raise typer.Exit(0)

            # 3. 标记为 ready（现有逻辑）
            service = PRService()
            pr = service.mark_ready(pr_number)

            if json_output:
                typer.echo(json.dumps(pr.model_dump(), indent=2, default=str))
            elif yaml_output:
                import yaml

                typer.echo(
                    yaml.dump(
                        pr.model_dump(), default_flow_style=False, allow_unicode=True
                    )
                )
            else:
                render_pr_ready(pr)

    @app.command()
    def merge(
        pr_number: Annotated[int, typer.Argument(help="PR number")],
        yes: Annotated[
            bool, typer.Option("-y", "--yes", help="自动确认（跳过交互）")
        ] = False,  # noqa: E501
        force: Annotated[
            bool, typer.Option("--force", help="强制合并（跳过安全检查）")
        ] = False,  # noqa: E501
        trace: Annotated[
            bool, typer.Option("--trace", help="启用调用链路追踪 + DEBUG 日志")
        ] = False,
        json_output: Annotated[
            bool, typer.Option("--json", help="JSON 格式输出")
        ] = False,  # noqa: E501
        yaml_output: Annotated[
            bool, typer.Option("--yaml", help="YAML 格式输出")
        ] = False,  # noqa: E501
    ) -> None:
        """Merge PR with safety checks.

        安全检查:
        - PR 已标记为 ready for review
        - CI 检查已通过
        - 无未处理的 review comments（可选）

        使用 --force 跳过所有检查（不推荐）.
        """
        if json_output and yaml_output:
            typer.echo("Error: Cannot use both --json and --yaml", err=True)
            raise typer.Exit(1)

        if trace:
            setup_logging(verbose=2)

        ctx = (
            trace_context(command="pr merge", domain="pr", pr_number=pr_number)
            if trace
            else noop_context()
        )
        with ctx:
            logger.bind(command="pr merge", pr_number=pr_number, force=force).info(
                "Merging PR"
            )

            # 1. 安全检查（除非 --force）
            if not force:
                from rich.console import Console

                console = Console()

                service = PRService()
                pr = service.get_pr(pr_number)

                if not pr:
                    logger.error("PR not found")
                    raise typer.Exit(1)

                # 1.1 检查 ready 状态
                if not pr.is_ready:
                    console.print("\n[red]✗ PR 未准备好合并[/]")
                    console.print(
                        f"[yellow]请先运行 `vibe pr ready {pr_number}` 标记为 ready[/]"
                    )
                    raise typer.Exit(1)

                # 1.2 检查 CI 状态
                if not pr.ci_passed:
                    console.print("\n[red]✗ CI 检查未通过[/]")
                    console.print("[yellow]请先修复 CI 问题[/]")
                    raise typer.Exit(1)

                # 1.3 检查 pending review comments（可选，优雅降级）
                # TODO: Implement pending review comments check
                # This functionality was removed as part of PR review refactoring
                # Pass silently for now

                # 显示通过信息
                console.print("\n[green]✓ 安全检查通过[/]")

            else:
                from rich.console import Console

                console = Console()
                console.print("\n[yellow]⚠️  强制合并（跳过安全检查）[/]")

            # 2. 确认操作（除非 --yes）
            if not yes:
                confirmed = typer.confirm(f"Merge PR #{pr_number}? (irreversible)")
                if not confirmed:
                    logger.info("Aborted by user")
                    raise typer.Exit(0)

            # 3. 执行合并（现有逻辑）
            service = PRService()
            pr = service.merge_pr(pr_number)

            if json_output:
                typer.echo(json.dumps(pr.model_dump(), indent=2, default=str))
            elif yaml_output:
                import yaml

                typer.echo(
                    yaml.dump(
                        pr.model_dump(), default_flow_style=False, allow_unicode=True
                    )
                )
            else:
                render_pr_merged(pr)
