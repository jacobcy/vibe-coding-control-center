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
            typer.Argument(
                help="Base branch to compare against (default: origin/main)"
            ),
        ] = "origin/main",
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
            vibe inspect base                # Compare current branch vs origin/main
            vibe inspect base origin/develop # Compare current branch vs origin/develop
            vibe inspect base main           # Compare current branch vs local main
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

        from vibe3.exceptions import GitError, UserError

        # Validate base branch exists
        git_client = GitClient()

        # Helper to check if a ref exists
        def ref_exists(ref: str) -> bool:
            try:
                git_client._run(["rev-parse", "--verify", ref])
                return True
            except GitError:
                return False

        # Check various ref formats
        base_exists = (
            ref_exists(base_branch)  # As provided (could be SHA, HEAD~5, etc.)
            or ref_exists(f"refs/heads/{base_branch}")  # Local branch
            or ref_exists(f"refs/remotes/{base_branch}")  # Remote ref (origin/main)
            or ref_exists(f"refs/remotes/origin/{base_branch}")  # Shorthand remote
        )

        if not base_exists:
            raise UserError(
                f"Base branch '{base_branch}' not found or invalid.\n\n"
                "Please provide a valid branch name or commit SHA.\n\n"
                "Examples:\n"
                "  vibe inspect base              # Use default: origin/main\n"
                "  vibe inspect base main         # Compare vs local main\n"
                "  vibe inspect base develop      # Compare vs develop branch\n"
                "  vibe inspect base HEAD~5       # Compare vs 5 commits ago"
            ) from None

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
        changed_lines = sum(
            1
            for line in git.get_diff(source).splitlines()
            if (line.startswith("+") or line.startswith("-"))
            and not line.startswith("+++")
            and not line.startswith("---")
        )

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
            from vibe3.services.pr_scoring_service import (
                PRDimensions,
                generate_score_report,
            )

            # Get AST-level analysis: changed functions
            # Skip test files - they don't need AST analysis
            changed_symbols_by_file: dict[str, list[str]] = {}
            skipped_tests = 0
            if existing_files:
                import sys

                from vibe3.services.serena_service import SerenaService

                svc = SerenaService(git_client=git)
                for file in existing_files:
                    # Skip test files to save tokens
                    is_test = (
                        file.startswith("tests/")
                        or file.startswith("test/")
                        or "/tests/" in file
                        or "/test/" in file
                        or file.startswith("test_")
                        or file.endswith("_test.py")
                    )
                    if is_test:
                        skipped_tests += 1
                        continue

                    if file.endswith(".py"):
                        try:
                            changed_funcs = svc.get_changed_functions(
                                file, source=source
                            )
                            if changed_funcs:
                                changed_symbols_by_file[file] = changed_funcs
                        except Exception:
                            # Skip files that can't be analyzed
                            pass

            if skipped_tests > 0:
                print(
                    f"[INFO] Skipped {skipped_tests} test files for AST analysis",
                    file=sys.stderr,
                )

            # Calculate score
            has_critical = any(f["critical_path"] for f in core_files)
            has_public_api = any(f["public_api"] for f in core_files)

            # Get impacted modules for scoring
            impacted_modules = []
            if core_files:
                # Only use existing files for DAG analysis
                core_paths = [
                    f["path"] for f in core_files if not f.get("deleted", False)
                ]
                if core_paths:
                    dag = dag_service.expand_impacted_modules(core_paths)
                    impacted_modules = dag.impacted_modules

            dims = PRDimensions(
                changed_files=len(all_changed_files),  # Include deleted files in count
                changed_lines=changed_lines,
                impacted_modules=len(impacted_modules),
                critical_path_touch=has_critical,
                public_api_touch=has_public_api,
            )
            score_report = generate_score_report(dims)

            result = {
                "current_branch": current_branch,
                "base_branch": base_branch,
                "core_files": core_files,
                "total_changed": len(all_changed_files),  # Include deleted files
                "existing_changed": len(existing_files),
                "deleted_files": len(deleted_files),
                "core_changed": len(core_files),
                "score": score_report,  # Add score for pre-push hook
            }
            if core_files:
                result["impacted_modules"] = impacted_modules
            if changed_symbols_by_file:
                result["changed_symbols"] = changed_symbols_by_file

            typer.echo(json.dumps(result, indent=2, default=str))
            return

        # Human-readable output
        typer.echo(f"=== Branch Analysis: {current_branch} vs {base_branch} ===\n")

        if deleted_files:
            typer.echo(f"⚠️  Deleted files: {len(deleted_files)}")
            for f in deleted_files[:5]:  # Show first 5
                typer.echo(f"    - {f}")
            if len(deleted_files) > 5:
                typer.echo(f"    ... and {len(deleted_files) - 5} more")
            typer.echo()

        if not core_files:
            typer.echo("✅ No core files changed")
            typer.echo(f"\n  Total files changed: {len(all_changed_files)}")
            typer.echo(f"  Existing files: {len(existing_files)}")
            typer.echo(f"  Deleted files: {len(deleted_files)}")
            typer.echo("  Core files changed: 0")
            return

        typer.echo(f"Core files changed ({len(core_files)}):")
        for file_info in core_files:
            tags = []
            if file_info["critical_path"]:
                tags.append("critical")
            if file_info["public_api"]:
                tags.append("public-api")
            if file_info.get("deleted"):
                tags.append("deleted")
            tag_str = ", ".join(tags)
            typer.echo(f"  - {file_info['path']} ({tag_str})")

        # Only analyze existing files for DAG impact
        existing_core_paths = [
            f["path"] for f in core_files if not f.get("deleted", False)
        ]
        if existing_core_paths:
            dag = dag_service.expand_impacted_modules(existing_core_paths)

            typer.echo(f"\nImpact scope ({len(dag.impacted_modules)} modules):")
            for module in dag.impacted_modules[:10]:
                typer.echo(f"  - {module}")
            if len(dag.impacted_modules) > 10:
                typer.echo(f"  ... and {len(dag.impacted_modules) - 10} more")
        else:
            typer.echo("\nImpact scope: No existing core files to analyze")

        typer.echo("\nSummary:")
        typer.echo(f"  Total files changed: {len(all_changed_files)}")
        typer.echo(f"  Existing files: {len(existing_files)}")
        typer.echo(f"  Deleted files: {len(deleted_files)}")
        typer.echo(f"  Core files changed: {len(core_files)}")

        critical_count = sum(1 for f in core_files if f["critical_path"])
        if critical_count > 0:
            typer.echo(f"  ⚠️  {critical_count} critical file(s) changed")
        else:
            typer.echo("  ℹ️  Only public API files changed")
