"""GovernanceService: periodic governance scan via configurable prompt composition.

Runs governance periodically to:
- Adjust issue labels and priorities
- Analyze dependencies
- Assign ready issues to manager agent

The service does NOT make decisions itself. It gathers runtime materials,
renders a configurable governance prompt via PromptAssembler, and invokes
`vibe3 run --plan`.
"""

from __future__ import annotations

import asyncio
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.event_bus import GitHubEvent, ServiceBase
from vibe3.orchestra.services.status_service import (
    IssueStatusEntry,
    OrchestraSnapshot,
    OrchestraStatusService,
)
from vibe3.prompts.assembler import PromptAssembler
from vibe3.prompts.models import (
    PromptRecipe,
    PromptRenderResult,
    PromptVariableSource,
    VariableSourceKind,
)
from vibe3.prompts.provider_registry import ProviderRegistry
from vibe3.prompts.template_loader import DEFAULT_PROMPTS_PATH

if TYPE_CHECKING:
    from vibe3.orchestra.dispatcher import Dispatcher

# Runtime variable keys that come from the snapshot (resolved as providers).
_GOVERNANCE_RUNTIME_VARS = (
    "server_status",
    "active_count",
    "active_flows",
    "active_worktrees",
    "running_issue_count",
    "suggested_issue_count",
    "circuit_breaker_state",
    "circuit_breaker_failures",
    "issue_list",
    "running_issue_details",
    "suggested_issue_details",
    "truncated_note",
)


class GovernanceService(ServiceBase):
    """Periodic governance scan service.

    Runs governance prompt composition on a configurable interval to maintain
    issue queue health. Does not handle webhook events - only tick-based.

    Execution is delegated to Dispatcher.run_governance_command() so that
    circuit breaker protection and error classification apply uniformly
    to both manager dispatch and governance scans.
    """

    event_types: list[str] = []

    def __init__(
        self,
        config: OrchestraConfig,
        status_service: OrchestraStatusService,
        dispatcher: Dispatcher,
        executor: ThreadPoolExecutor | None = None,
        prompts_path: Path | None = None,
    ) -> None:
        self.config = config
        self._status_service = status_service
        self._dispatcher = dispatcher
        self._executor = executor or ThreadPoolExecutor(max_workers=1)
        self._tick_count = 0
        self._skill = config.governance.skill
        self._prompt_template = config.governance.prompt_template
        self._include_skill_content = config.governance.include_skill_content
        self._dry_run = config.governance.dry_run
        self._prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
        # Populated after each _render_governance_plan call; used by dry-run logging.
        self.last_render_result: PromptRenderResult | None = None

    async def handle_event(self, event: GitHubEvent) -> None:
        """No-op: governance service is tick-based only."""
        pass

    async def on_tick(self) -> None:
        """Run governance scan on interval."""
        self._tick_count += 1

        if self._tick_count % self.config.governance.interval_ticks != 0:
            return

        log = logger.bind(domain="orchestra", action="governance")
        log.info(f"Running governance scan (tick #{self._tick_count})")

        try:
            await self._run_governance()
        except Exception as exc:
            log.error(f"Governance scan failed: {exc}")

    async def _run_governance(self) -> None:
        """Execute governance scan."""
        loop = asyncio.get_running_loop()
        log = logger.bind(domain="orchestra", action="governance")

        snapshot = await loop.run_in_executor(
            self._executor, self._status_service.snapshot
        )

        if snapshot.circuit_breaker_state == "open":
            log.warning("Skipping governance: circuit breaker is OPEN")
            return

        context = self._build_prompt_context(snapshot)
        plan_content = self._render_governance_plan(context)

        if self._dry_run:
            dry_run_plan_path = self._write_dry_run_plan(plan_content)
            cmd = self._build_governance_command(dry_run_plan_path)
            self._log_dry_run_preview(
                log, context, dry_run_plan_path, cmd, plan_content
            )
            return

        plan_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".md",
                prefix="governance_plan_",
                delete=False,
            ) as handle:
                handle.write(plan_content)
                plan_path = Path(handle.name)

            cmd = self._build_governance_command(plan_path)
            log.info(f"Executing governance: {' '.join(cmd)}")

            success = await loop.run_in_executor(
                self._executor,
                lambda: self._dispatcher.run_governance_command(cmd, "Governance scan"),
            )

            if success:
                log.info("Governance scan completed successfully")
            else:
                log.warning("Governance scan returned non-zero exit code")
        finally:
            if plan_path:
                plan_path.unlink(missing_ok=True)

    def _build_governance_plan(self, snapshot: OrchestraSnapshot) -> str:
        """Build governance plan content from snapshot."""
        context = self._build_prompt_context(snapshot)
        return self._render_governance_plan(context)

    def _build_governance_recipe(self) -> PromptRecipe:
        """Build the PromptRecipe for governance rendering.

        skill_name and skill_content use static sources (literal / skill).
        All snapshot-derived runtime variables use provider sources; the
        registry is populated with closures at render time.
        """
        skill_content_source = (
            PromptVariableSource(kind=VariableSourceKind.SKILL, skill=self._skill)
            if self._include_skill_content
            else PromptVariableSource(kind=VariableSourceKind.LITERAL, value="")
        )
        variables: dict[str, PromptVariableSource] = {
            "skill_name": PromptVariableSource(
                kind=VariableSourceKind.LITERAL, value=self._skill
            ),
            "skill_content": skill_content_source,
        }
        for key in _GOVERNANCE_RUNTIME_VARS:
            variables[key] = PromptVariableSource(
                kind=VariableSourceKind.PROVIDER,
                provider=f"governance.{key}",
            )
        return PromptRecipe(
            template_key=self._prompt_template,
            variables=variables,
            description="Orchestra governance scan",
        )

    def _render_governance_plan(self, context: dict[str, Any]) -> str:
        """Render governance plan using PromptAssembler with recipe-driven assembly."""
        recipe = self._build_governance_recipe()
        registry = _build_runtime_registry(context)
        assembler = PromptAssembler(prompts_path=self._prompts_path, registry=registry)
        result = assembler.render(recipe, runtime_context=context)
        self.last_render_result = result
        return result.rendered_text

    def _build_governance_command(self, plan_path: Path) -> list[str]:
        return [
            "uv",
            "run",
            "python",
            "-m",
            "vibe3",
            "run",
            "--plan",
            str(plan_path),
        ]

    def _write_dry_run_plan(self, plan_content: str) -> Path:
        output_dir = self._dispatcher.repo_path / "temp"
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            prefix="governance_dry_run_",
            dir=output_dir,
            delete=False,
        ) as handle:
            handle.write(plan_content)
            return Path(handle.name)

    def _log_dry_run_preview(
        self,
        log: Any,
        context: dict[str, Any],
        plan_path: Path,
        cmd: list[str],
        plan_content: str,
    ) -> None:
        sources = self._build_material_source_summary()
        log.info("Dry run: governance plan prepared")
        log.info(
            f"Governance prompt source: {sources['prompt_template_file']}"
            f"#{sources['prompt_template_key']}"
        )
        log.info(
            f"Governance skill source: {sources['skill_name']} -> "
            f"{sources['skill_file']}"
        )
        if self.last_render_result:
            provider_keys = [
                p.variable
                for p in self.last_render_result.provenance
                if p.source_kind == VariableSourceKind.PROVIDER
            ]
            log.info(f"Provider keys: {sorted(provider_keys)}")
        log.info(
            f"Include skill content: {self._include_skill_content}; "
            f"prompt vars={sorted(context.keys())}"
        )
        log.info(f"Dry run plan file: {plan_path}")
        log.info(f"Dry run command: {' '.join(cmd)}")
        log.info("Dry run rendered governance plan:")
        log.info(f"\n{plan_content}")

    def _build_prompt_context(self, snapshot: OrchestraSnapshot) -> dict[str, Any]:
        """Build runtime context dict from snapshot.

        Does not include skill_name or skill_content — those are declared as
        static sources in the recipe returned by _build_governance_recipe().
        """
        active_entries = snapshot.active_issues
        active_count = len(active_entries)
        running_entries = tuple(
            entry for entry in active_entries if self._is_running_issue(entry)
        )
        suggested_entries = tuple(
            entry for entry in active_entries if not self._is_running_issue(entry)
        )
        issue_list = (
            "\n".join(
                self._format_issue_summary_line(entry) for entry in active_entries[:20]
            )
            or "(无活跃 issue)"
        )
        running_issue_details = (
            "\n".join(
                self._format_issue_runtime_line(entry) for entry in running_entries[:20]
            )
            or "(无 running issues)"
        )
        suggested_issue_details = (
            "\n".join(
                self._format_issue_runtime_line(entry)
                for entry in suggested_entries[:20]
            )
            or "(无建议 issue)"
        )
        truncated_note = ""
        if active_count > 20:
            truncated_note = (
                f"\n(已截断，仅显示前 20 条 / 共 {active_count} 条活跃 issue)"
            )

        return {
            "server_status": "running" if snapshot.server_running else "stopped",
            "active_count": active_count,
            "active_flows": snapshot.active_flows,
            "active_worktrees": snapshot.active_worktrees,
            "running_issue_count": len(running_entries),
            "suggested_issue_count": len(suggested_entries),
            "circuit_breaker_state": snapshot.circuit_breaker_state,
            "circuit_breaker_failures": snapshot.circuit_breaker_failures,
            "issue_list": issue_list,
            "running_issue_details": running_issue_details,
            "suggested_issue_details": suggested_issue_details,
            "truncated_note": truncated_note,
        }

    def _is_running_issue(self, entry: IssueStatusEntry) -> bool:
        return entry.has_flow or entry.has_worktree or entry.has_pr

    def _format_issue_summary_line(self, entry: IssueStatusEntry) -> str:
        state_label = entry.state.to_label() if entry.state else "state/unknown"
        blocked_by = ", ".join(f"#{number}" for number in entry.blocked_by)
        blocked = f" [blocked_by={blocked_by}]" if entry.blocked_by else ""
        return f"- #{entry.number}: {entry.title[:60]} | {state_label}{blocked}"

    def _format_issue_runtime_line(self, entry: IssueStatusEntry) -> str:
        state_label = entry.state.to_label() if entry.state else "state/unknown"
        flow_value = entry.flow_branch or "(not started)"
        worktree_value = entry.worktree_path or "(none)"
        pr_value = f"#{entry.pr_number}" if entry.pr_number is not None else "(none)"
        parts = [
            f"- #{entry.number}: {entry.title[:60]}",
            state_label,
            f"assignee={entry.assignee or '(unassigned)'}",
            f"flow={flow_value}",
            f"worktree={worktree_value}",
            f"pr={pr_value}",
        ]
        if entry.blocked_by:
            blocked_by = ", ".join(f"#{number}" for number in entry.blocked_by)
            parts.append(f"blocked_by={blocked_by}")
        return " | ".join(parts)

    def _build_material_source_summary(self) -> dict[str, str]:
        prompts_path = self._resolve_prompts_path()
        skill_path = self._resolve_skill_path()
        return {
            "prompt_template_key": self._prompt_template,
            "prompt_template_file": str(prompts_path),
            "skill_name": self._skill,
            "skill_file": str(skill_path) if skill_path is not None else "(not found)",
        }

    def _resolve_prompts_path(self) -> Path:
        if self._prompts_path.is_absolute():
            return self._prompts_path
        return Path.cwd() / self._prompts_path

    def _resolve_skill_path(self) -> Path | None:
        from vibe3.agents.run_agent import RunUsecase

        return RunUsecase.find_skill_file(self._skill)


def _build_runtime_registry(context: dict[str, Any]) -> ProviderRegistry:
    """Build a ProviderRegistry with closures for all governance runtime vars."""
    registry = ProviderRegistry()

    def create_provider(value: str) -> Callable[[Any], str]:
        def provider(_: Any) -> str:
            return value

        return provider

    for key in _GOVERNANCE_RUNTIME_VARS:
        value = str(context.get(key, ""))
        registry.register(f"governance.{key}", create_provider(value))
    return registry
