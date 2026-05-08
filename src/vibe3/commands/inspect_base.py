"""Inspect base command - 分支对比核心文件改动分析."""

import json
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from loguru import logger

from vibe3.commands.inspect_base_helpers import (
    build_json_output,
    count_changed_lines_in_code_paths,
    print_human_output,
    validate_base_branch,
)
from vibe3.commands.pr_helpers import build_base_resolution_usecase
from vibe3.utils.trace import enable_trace


def register(app: typer.Typer) -> None:
    """Register the base command on the given app."""

    @app.command()
    def base(
        base_branch: Annotated[
            str | None,
            typer.Argument(
                help=(
                    "Base policy/branch: parent|current|main|<branch> "
                    "(default: parent)"
                )
            ),
        ] = None,
        json_out: Annotated[
            bool, typer.Option("--json", help="Output as JSON")
        ] = False,
        yaml_out: Annotated[
            bool, typer.Option("--yaml", help="Output as YAML")
        ] = False,
        quiet: Annotated[
            bool, typer.Option("--quiet", help="Suppress next step suggestions")
        ] = False,
        trace: Annotated[
            bool, typer.Option("--trace", help="Enable call tracing + DEBUG logs")
        ] = False,
    ) -> None:
        """Analyze core file changes between current branch and base branch.

        Focus on critical paths and public API files only.
        Shows impact scope, not detailed diffs.

        Examples:
            vibe inspect base                # Compare current branch vs parent branch
            vibe inspect base origin/develop # Compare current branch vs origin/develop
            vibe inspect base main           # Compare current branch vs origin/main
        """
        from vibe3.clients.git_client import GitClient
        from vibe3.clients.github_client import GitHubClient
        from vibe3.config.loader import get_config
        from vibe3.models.change_source import BranchSource
        from vibe3.utils.git_helpers import get_current_branch

        if trace:
            enable_trace()

        current_branch = get_current_branch()
        resolved = build_base_resolution_usecase().resolve_inspect_base(
            base_branch,
            current_branch=current_branch,
        )
        resolved_base = resolved.base_branch

        # Validate base branch exists
        git_client = GitClient()
        validate_base_branch(git_client, resolved_base)

        log = logger.bind(
            domain="inspect",
            action="base_analysis",
            current_branch=current_branch,
            base_branch=resolved_base,
        )
        log.info("Analyzing core file changes")

        git = GitClient(github_client=GitHubClient())
        source = BranchSource(branch=current_branch, base=resolved_base)
        all_changed_files = git.get_changed_files(source)

        # Count changed lines only in code paths
        changed_lines = count_changed_lines_in_code_paths(git, source)

        # Track all files for scoring, but note which ones are deleted
        # Deleted files should still participate in risk assessment
        existing_files = [f for f in all_changed_files if Path(f).exists()]
        deleted_files = [f for f in all_changed_files if not Path(f).exists()]

        if deleted_files:
            log.bind(
                total_files=len(all_changed_files),
                existing_files=len(existing_files),
                deleted_files=len(deleted_files),
            ).warning(
                f"Found {len(deleted_files)} deleted files "
                "- including in risk assessment"
            )

        config = get_config()
        critical_paths = config.review_scope.critical_paths
        public_api_paths = config.review_scope.public_api_paths

        core_files: list[dict[str, Any]] = []
        # Check all files (including deleted) for critical/public_api status
        for file in all_changed_files:
            is_critical = any(p in str(file) for p in critical_paths)
            is_public_api = any(p in str(file) for p in public_api_paths)
            if is_critical or is_public_api:
                core_files.append(
                    {
                        "path": file,
                        "critical_path": is_critical,
                        "public_api": is_public_api,
                        "deleted": not Path(file).exists(),
                    }
                )

        if json_out:
            result = build_json_output(
                git=git,
                source=source,
                current_branch=current_branch,
                base_branch=resolved_base,
                all_changed_files=all_changed_files,
                existing_files=existing_files,
                deleted_files=deleted_files,
                core_files=core_files,
                changed_lines=changed_lines,
            )
            typer.echo(json.dumps(result, indent=2, default=str))
            return
        elif yaml_out:
            result = build_json_output(
                git=git,
                source=source,
                current_branch=current_branch,
                base_branch=resolved_base,
                all_changed_files=all_changed_files,
                existing_files=existing_files,
                deleted_files=deleted_files,
                core_files=core_files,
                changed_lines=changed_lines,
            )
            # Convert to JSON-serializable dict first (handles enums, etc.)
            clean_result = json.loads(json.dumps(result, default=str))
            typer.echo(
                yaml.dump(clean_result, default_flow_style=False, allow_unicode=True)
            )
            return

        # Human-readable output
        print_human_output(
            current_branch=current_branch,
            base_branch=resolved_base,
            all_changed_files=all_changed_files,
            existing_files=existing_files,
            deleted_files=deleted_files,
            core_files=core_files,
        )

        from vibe3.commands.inspect_helpers import suggest_next_step

        suggest_next_step("inspect_base", quiet)
