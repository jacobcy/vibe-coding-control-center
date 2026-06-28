"""Git-backed branch observation for the inspect command group."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
import yaml

from vibe3.analysis.review_observation import build_review_observation
from vibe3.commands.common import enable_method_trace
from vibe3.commands.inspect_base_helpers import render_review_observation
from vibe3.commands.pr_helpers import build_base_resolution_usecase


def register(app: typer.Typer) -> None:
    """Register the evidence-only base command."""

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
            bool,
            typer.Option("--trace", help="Enable call tracing (set VIBE3_TRACE=1)"),
        ] = False,
    ) -> None:
        """Show exact Git changes and deterministic Kernel review evidence."""
        from vibe3.clients import GitClient
        from vibe3.services.flow import FlowService
        from vibe3.utils import get_current_branch

        del quiet
        if trace:
            enable_method_trace()

        current_branch = get_current_branch()
        flow_state = FlowService().get_flow_status(current_branch)
        creation_source = flow_state.creation_source if flow_state else None
        resolved = build_base_resolution_usecase().resolve_inspect_base(
            base_branch,
            current_branch=current_branch,
            creation_source=creation_source,
        )

        git = GitClient()
        manifest_path = (
            Path(git.get_worktree_root()) / "config" / "v3" / "review_kernel.yaml"
        )
        observation = build_review_observation(
            requested_base=base_branch,
            resolved_base=resolved.base_branch,
            git=git,
            manifest_path=manifest_path,
        )

        if json_out:
            typer.echo(observation.model_dump_json(indent=2))
        elif yaml_out:
            payload = json.loads(observation.model_dump_json())
            typer.echo(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
        else:
            typer.echo(render_review_observation(observation))

        if observation.status == "error":
            raise typer.Exit(1)
