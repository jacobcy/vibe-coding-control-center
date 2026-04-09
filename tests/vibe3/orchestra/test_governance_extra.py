"""Tests for GovernanceService."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.models.orchestra_config import GovernanceConfig, OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.services.orchestra_status_service import (
    OrchestraSnapshot,
)


class MockStatusService:
    """Mock status service for testing."""

    def __init__(self, snapshot: OrchestraSnapshot | None = None):
        self._snapshot = snapshot

    def snapshot(self) -> OrchestraSnapshot:
        if self._snapshot:
            return self._snapshot
        return OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )


def _make_dispatcher(
    run_result: bool = True, repo_path: Path | None = None
) -> MagicMock:
    """Create a mock manager-like dependency with repo_path."""
    dispatcher = MagicMock()
    dispatcher.repo_path = repo_path or Path("/tmp/vibe-repo")
    return dispatcher


class TestGovernanceService:
    """Tests for GovernanceService."""

    def test_build_governance_plan_can_disable_supervisor_content(self, tmp_path):
        """Governance prompt template should allow omitting supervisor body."""
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            "orchestra:\n"
            "  governance:\n"
            "    plan: |\n"
            "      Supervisor={supervisor_name}\n"
            "      Content={supervisor_content}\n"
        )
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(
                    dry_run=True,
                    prompt_template="orchestra.governance.plan",
                    include_supervisor_content=False,
                )
            ),
            status_service=MockStatusService(snapshot),
            manager=_make_dispatcher(),
            prompts_path=prompts_path,
        )

        plan = service._build_governance_plan(snapshot)
        assert "Supervisor=supervisor/orchestra.md" in plan
        assert "Content=" in plan
        assert "自动化治理材料" not in plan

    def test_build_material_source_summary_reports_configured_sources(
        self, tmp_path, monkeypatch
    ):
        """Dry run metadata points to configured prompt and supervisor sources."""
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            "orchestra:\n" "  governance:\n" "    plan: |\n" "      Prompt body\n"
        )
        supervisor_dir = tmp_path / "supervisor"
        supervisor_dir.mkdir()
        supervisor_path = supervisor_dir / "demo.md"
        supervisor_path.write_text("# Demo Supervisor\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(
                    supervisor_file="supervisor/demo.md",
                    prompt_template="orchestra.governance.plan",
                )
            ),
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
            prompts_path=prompts_path,
        )

        summary = service._build_material_source_summary()

        assert summary["prompt_template_key"] == "orchestra.governance.plan"
        assert summary["prompt_template_file"] == str(prompts_path)
        assert summary["supervisor_file"] == "supervisor/demo.md"
        assert summary["supervisor_path"] == str(supervisor_path)

    @pytest.mark.asyncio
    async def test_run_governance_honors_governance_dry_run(self, tmp_path):
        """Dry run stops before dispatch and persists a preview plan under temp/."""
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        service = GovernanceService(
            config=OrchestraConfig(governance=GovernanceConfig(dry_run=True)),
            status_service=MockStatusService(snapshot),
            manager=_make_dispatcher(repo_path=tmp_path),
            backend=MagicMock(),
        )

        prompt, options, task = await service.build_governance_execution_payload()
        assert prompt is None

        dry_run_files = sorted(
            (tmp_path / "temp" / "logs" / "orchestra" / "governance" / "dry-run").glob(
                "governance_dry_run_*.md"
            )
        )
        assert len(dry_run_files) == 1
        assert "# Orchestra Governance Scan" in dry_run_files[0].read_text()

    @pytest.mark.asyncio
    async def test_run_governance_dispatches_async_when_not_dry_run(self, tmp_path):
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        service = GovernanceService(
            config=OrchestraConfig(governance=GovernanceConfig(dry_run=False)),
            status_service=MockStatusService(snapshot),
            manager=_make_dispatcher(repo_path=tmp_path),
            backend=MagicMock(),
        )

        prompt, options, task = await service.build_governance_execution_payload()

        assert prompt is not None
        assert options is not None
        assert "governance scan" in task

    @pytest.mark.asyncio
    async def test_on_tick_is_stub_does_not_dispatch(self, tmp_path, monkeypatch):
        """on_tick() is a stub and must NOT dispatch.

        Governance skipping when a live session exists is now handled by
        CapacityService in the domain handler (GovernanceScanStarted).
        """
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(interval_ticks=1, dry_run=False)
            ),
            status_service=MockStatusService(snapshot),
            manager=_make_dispatcher(repo_path=tmp_path),
            backend=MagicMock(),
        )

        run_called = {"count": 0}

        async def fake_run() -> None:
            run_called["count"] += 1

        monkeypatch.setattr(service, "build_governance_execution_payload", fake_run)

        await service.on_tick()

        # Domain-first: on_tick() is a stub — must NOT dispatch
        assert run_called["count"] == 0
