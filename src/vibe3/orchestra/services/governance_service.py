"""GovernanceService: periodic governance scan via configurable prompt composition."""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from vibe3.agents.backends.codeagent import AsyncExecutionHandle, CodeagentBackend
from vibe3.environment.session_registry import SessionRegistryService
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.orchestra.logging import (
    append_governance_event,
    governance_dry_run_dir,
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
from vibe3.runtime.agent_resolver import resolve_governance_agent_options
from vibe3.runtime.event_bus import GitHubEvent, ServiceBase
from vibe3.services.orchestra_status_service import (
    OrchestraSnapshot,
    OrchestraStatusService,
    format_issue_runtime_line,
    format_issue_summary_line,
    is_running_issue,
)

if TYPE_CHECKING:
    from vibe3.manager.manager_executor import ManagerExecutor

# Runtime variable keys that come from the snapshot (resolved as providers).
_GOVERNANCE_RUNTIME_VARS = (
    "server_status",
    "active_count",
    "active_flows",
    "active_worktrees",
    "running_issue_count",
    "queued_issue_count",
    "suggested_issue_count",
    "circuit_breaker_state",
    "circuit_breaker_failures",
    "issue_list",
    "running_issue_details",
    "suggested_issue_details",
    "truncated_note",
)

GOVERNANCE_TASK_PROMPT = (
    "Run orchestra governance scan. "
    "Analyze the current runtime snapshot, follow the governance supervisor "
    "material only, produce governance conclusions or minimal allowed actions, "
    "then stop. Do not switch into execution-plan or implementation mode."
)


class GovernanceService(ServiceBase):
    """Periodic governance scan service.

    Execution uses the shared dispatcher executor directly with circuit
    breaker protection.
    """

    event_types: list[str] = []

    def __init__(
        self,
        config: OrchestraConfig,
        status_service: OrchestraStatusService,
        manager: ManagerExecutor | None = None,
        executor: ThreadPoolExecutor | None = None,
        prompts_path: Path | None = None,
        backend: CodeagentBackend | None = None,
        registry: SessionRegistryService | None = None,
    ) -> None:
        self.config = config
        self._status_service = status_service
        if manager is None:
            from vibe3.manager.manager_executor import (
                ManagerExecutor as _ManagerExecutor,
            )

            manager = _ManagerExecutor(config, dry_run=config.dry_run)
        self._manager = manager
        self._executor = executor or ThreadPoolExecutor(max_workers=1)
        self._tick_count = 0
        self._supervisor_file = config.governance.supervisor_file
        self._prompt_template = config.governance.prompt_template
        self._include_supervisor_content = config.governance.include_supervisor_content
        self._dry_run = config.governance.dry_run
        self._prompts_path = prompts_path or DEFAULT_PROMPTS_PATH
        self._backend = backend or CodeagentBackend()
        self._registry = registry
        self.last_render_result: PromptRenderResult | None = None

    async def handle_event(self, event: GitHubEvent) -> None:
        pass

    async def run_once(self) -> None:
        """Run governance exactly once for manual debugging."""
        await self._run_governance()

    async def run_scan(self) -> None:
        """Run governance scan (callable from domain handlers).

        This method provides a clean interface for domain handlers to
        trigger governance execution. It does not manage capacity or
        lifecycle - those should be handled by the caller (domain handler).
        """
        await self._run_governance()

    def render_current_plan(self) -> str:
        """Render governance plan from the current live snapshot."""
        snapshot = self._status_service.snapshot()
        return self._build_governance_plan(snapshot)

    async def _run_governance(self) -> None:
        loop = asyncio.get_event_loop()
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
            self._log_dry_run_preview(log, context, dry_run_plan_path, plan_content)
            return
        session_id: int | None = None
        if self._registry is not None:
            session_id = self._registry.reserve(
                role="governance",
                target_type="governance",
                target_id="scan",
                branch="governance",
            )
        try:
            handle = await loop.run_in_executor(
                self._executor,
                self._dispatch_governance_prompt,
                plan_content,
            )
        except Exception:
            # Clean up reserved session on dispatch failure
            if self._registry is not None and session_id is not None:
                self._registry.mark_failed(session_id)
            raise
        if self._registry is not None and session_id is not None:
            self._registry.mark_started(session_id, tmux_session=handle.tmux_session)
        log.info(
            "Governance scan dispatched",
            tmux_session=handle.tmux_session,
            log_path=str(handle.log_path),
        )
        append_governance_event(
            (
                f"tick #{self._tick_count} dispatched: "
                f"tmux={handle.tmux_session} log={handle.log_path}"
            ),
            repo_root=self._manager.repo_path,
        )

    def _build_governance_plan(self, snapshot: OrchestraSnapshot) -> str:
        context = self._build_prompt_context(snapshot)
        return self._render_governance_plan(context)

    def _build_governance_recipe(self) -> PromptRecipe:
        supervisor_content_source = (
            PromptVariableSource(
                kind=VariableSourceKind.FILE,
                path=self._supervisor_file,
            )
            if self._include_supervisor_content
            else PromptVariableSource(kind=VariableSourceKind.LITERAL, value="")
        )
        variables: dict[str, PromptVariableSource] = {
            "supervisor_name": PromptVariableSource(
                kind=VariableSourceKind.LITERAL, value=self._supervisor_file
            ),
            "supervisor_content": supervisor_content_source,
        }
        for key in _GOVERNANCE_RUNTIME_VARS:
            variables[key] = PromptVariableSource(
                kind=VariableSourceKind.PROVIDER, provider=f"governance.{key}"
            )
        return PromptRecipe(
            template_key=self._prompt_template,
            variables=variables,
            description="Orchestra governance scan",
        )

    def _render_governance_plan(self, context: dict[str, Any]) -> str:
        recipe = self._build_governance_recipe()
        registry = _build_runtime_registry(context)
        assembler = PromptAssembler(prompts_path=self._prompts_path, registry=registry)
        result = assembler.render(recipe, runtime_context=context)
        self.last_render_result = result
        return result.rendered_text

    def _write_dry_run_plan(self, plan_content: str) -> Path:
        output_dir = governance_dry_run_dir(self._manager.repo_path)
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
        plan_content: str,
    ) -> None:
        sources = self._build_material_source_summary()
        log.info("Dry run: governance plan prepared")
        log.info(
            f"Governance prompt source: {sources['prompt_template_file']} "
            f"#{sources['prompt_template_key']}"
        )
        log.info(
            f"Governance supervisor source: {sources['supervisor_file']} -> "
            f"{sources['supervisor_path']}"
        )
        if self.last_render_result:
            provider_keys = [
                p.variable
                for p in self.last_render_result.provenance
                if p.source_kind == VariableSourceKind.PROVIDER
            ]
            log.info(f"Provider keys: {sorted(provider_keys)}")
        log.info(
            f"Include supervisor content: {self._include_supervisor_content}; "
            f"prompt vars={sorted(context.keys())}"
        )
        log.info(f"Dry run plan file: {plan_path}")
        append_governance_event(
            f"dry-run plan written: {plan_path}",
            repo_root=self._manager.repo_path,
        )
        log.info("Dry run rendered governance plan:")
        log.info(f"\n{plan_content}")

    def _dispatch_governance_prompt(self, prompt: str) -> AsyncExecutionHandle:
        options = resolve_governance_agent_options(self.config)
        return self._backend.start_async(
            prompt=prompt,
            options=options,
            task=GOVERNANCE_TASK_PROMPT,
            execution_name=self._governance_execution_name(),
            env={**os.environ, "VIBE3_ASYNC_CHILD": "1"},
            keep_alive_seconds=0,
        )

    def _governance_execution_name(self) -> str:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"vibe3-governance-scan-{timestamp}-t{self._tick_count}"

    def _build_prompt_context(self, snapshot: OrchestraSnapshot) -> dict[str, Any]:
        active_entries = snapshot.active_issues
        active_count = len(active_entries)
        running_entries = tuple(
            entry for entry in active_entries if is_running_issue(entry)
        )
        suggested_entries = tuple(
            entry for entry in active_entries if not is_running_issue(entry)
        )
        issue_list = (
            "\n".join(format_issue_summary_line(entry) for entry in active_entries[:20])
            or "(无活跃 issue)"
        )
        running_issue_details = (
            "\n".join(
                format_issue_runtime_line(entry) for entry in running_entries[:20]
            )
            or "(无 running issues)"
        )
        suggested_issue_details = (
            "\n".join(
                format_issue_runtime_line(entry) for entry in suggested_entries[:20]
            )
            or "(无建议 issue)"
        )
        truncated_note = (
            f"\n(已截断，仅显示前 20 条 / 共 {active_count} 条活跃 issue)"
            if active_count > 20
            else ""
        )
        return {
            "server_status": "running" if snapshot.server_running else "stopped",
            "active_count": active_count,
            "active_flows": snapshot.active_flows,
            "active_worktrees": snapshot.active_worktrees,
            "running_issue_count": len(running_entries),
            "queued_issue_count": len(snapshot.queued_issues),
            "suggested_issue_count": len(suggested_entries),
            "circuit_breaker_state": snapshot.circuit_breaker_state,
            "circuit_breaker_failures": snapshot.circuit_breaker_failures,
            "issue_list": issue_list,
            "running_issue_details": running_issue_details,
            "suggested_issue_details": suggested_issue_details,
            "truncated_note": truncated_note,
        }

    def _build_material_source_summary(self) -> dict[str, str]:
        prompts_path = self._resolve_prompts_path()
        supervisor_path = self._resolve_supervisor_path()
        return {
            "prompt_template_key": self._prompt_template,
            "prompt_template_file": str(prompts_path),
            "supervisor_file": self._supervisor_file,
            "supervisor_path": (
                str(supervisor_path) if supervisor_path is not None else "(not found)"
            ),
        }

    def _resolve_prompts_path(self) -> Path:
        return (
            self._prompts_path
            if self._prompts_path.is_absolute()
            else Path.cwd() / self._prompts_path
        )

    def _resolve_supervisor_path(self) -> Path | None:
        path = Path(self._supervisor_file)
        if not path.is_absolute():
            path = Path.cwd() / path
        if path.exists():
            return path
        return None


def _build_runtime_registry(context: dict[str, Any]) -> ProviderRegistry:
    registry = ProviderRegistry()

    def create_provider(value: str) -> Callable[[Any], str]:
        return lambda _: value

    for key in _GOVERNANCE_RUNTIME_VARS:
        registry.register(
            f"governance.{key}", create_provider(str(context.get(key, "")))
        )
    return registry
