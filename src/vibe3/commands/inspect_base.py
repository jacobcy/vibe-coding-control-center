"""Inspect base command - 分支对比核心文件改动分析."""

from pathlib import Path
from typing import Annotated, Any

import typer
from loguru import logger

from vibe3.utils.trace import enable_trace


def register(app: typer.Typer) -> None:
    """Register the base command on the given app."""

    @app.command()
    def base(
        base_branch: Annotated[
            str,
            typer.Argument(help="Base branch to compare against (default: main)"),
        ] = "main",
        json_out: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        trace: Annotated[
            bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
        ] = False,
    ) -> None:
        """Analyze core file changes between current branch and base branch.

        Focus on critical paths and public API files only.
        Shows impact scope, not detailed diffs.

        Examples:
            vibe inspect base          # Compare current branch vs main
            vibe inspect base develop  # Compare current branch vs develop
        """
        import json

        from vibe3.clients.git_client import GitClient
        from vibe3.clients.github_client import GitHubClient
        from vibe3.config.loader import get_config
        from vibe3.models.change_source import BranchSource
        from vibe3.services import dag_service
        from vibe3.utils.git_helpers import get_current_branch

        if trace:
            enable_trace()

        current_branch = get_current_branch()

        log = logger.bind(
            domain="inspect",
            action="base_analysis",
            current_branch=current_branch,
            base_branch=base_branch,
        )
        log.info("Analyzing core file changes")

        git = GitClient(github_client=GitHubClient())
        source = BranchSource(branch=current_branch, base=base_branch)
        all_changed_files = git.get_changed_files(source)

        changed_files = [f for f in all_changed_files if Path(f).exists()]

        config = get_config()
        critical_paths = config.review_scope.critical_paths
        public_api_paths = config.review_scope.public_api_paths

        core_files: list[dict[str, Any]] = []
        for file in changed_files:
            is_critical = any(p in str(file) for p in critical_paths)
            is_public_api = any(p in str(file) for p in public_api_paths)
            if is_critical or is_public_api:
                core_files.append(
                    {
                        "path": file,
                        "critical_path": is_critical,
                        "public_api": is_public_api,
                    }
                )

        if json_out:
            result = {
                "current_branch": current_branch,
                "base_branch": base_branch,
                "core_files": core_files,
                "total_changed": len(changed_files),
                "core_changed": len(core_files),
            }
            if core_files:
                core_paths = [f["path"] for f in core_files]
                dag = dag_service.expand_impacted_modules(core_paths)
                result["impacted_modules"] = dag.impacted_modules

            typer.echo(json.dumps(result, indent=2, default=str))
            return

        # Human-readable output
        typer.echo(f"=== Branch Analysis: {current_branch} vs {base_branch} ===\n")

        if not core_files:
            typer.echo("✅ No core files changed")
            typer.echo(f"\n  Total files changed: {len(changed_files)}")
            typer.echo("  Core files changed: 0")
            return

        typer.echo(f"Core files changed ({len(core_files)}):")
        for file_info in core_files:
            tags = []
            if file_info["critical_path"]:
                tags.append("critical")
            if file_info["public_api"]:
                tags.append("public-api")
            tag_str = ", ".join(tags)
            typer.echo(f"  - {file_info['path']} ({tag_str})")

        core_paths = [f["path"] for f in core_files]
        dag = dag_service.expand_impacted_modules(core_paths)

        typer.echo(f"\nImpact scope ({len(dag.impacted_modules)} modules):")
        for module in dag.impacted_modules[:10]:
            typer.echo(f"  - {module}")
        if len(dag.impacted_modules) > 10:
            typer.echo(f"  ... and {len(dag.impacted_modules) - 10} more")

        typer.echo("\nSummary:")
        typer.echo(f"  Total files changed: {len(changed_files)}")
        typer.echo(f"  Core files changed: {len(core_files)}")

        critical_count = sum(1 for f in core_files if f["critical_path"])
        if critical_count > 0:
            typer.echo(f"  ⚠️  {critical_count} critical file(s) changed")
        else:
            typer.echo("  ℹ️  Only public API files changed")
