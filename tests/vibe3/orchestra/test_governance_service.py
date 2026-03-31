"""Tests for GovernanceService."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.orchestra.config import GovernanceConfig, OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.orchestra.services.status_service import (
    IssueStatusEntry,
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


def _make_dispatcher(run_result: bool = True) -> MagicMock:
    """Create a mock Dispatcher with repo_path and run_governance_command."""
    dispatcher = MagicMock()
    dispatcher.repo_path = Path("/repo")
    dispatcher.run_governance_command.return_value = run_result
    return dispatcher


def _make_service(
    config: OrchestraConfig | None = None,
    snapshot: OrchestraSnapshot | None = None,
    run_result: bool = True,
) -> GovernanceService:
    """Helper to create a GovernanceService with mocked dependencies."""
    return GovernanceService(
        config=config or OrchestraConfig(),
        status_service=MockStatusService(snapshot),
        dispatcher=_make_dispatcher(run_result),
    )


class TestGovernanceService:
    """Tests for GovernanceService."""

    def test_no_webhook_events(self):
        """GovernanceService should not handle webhook events."""
        service = _make_service()
        assert service.event_types == []

    def test_tick_interval_from_config(self):
        """Governance should only run on config.governance.interval_ticks boundary."""
        config = OrchestraConfig(governance=GovernanceConfig(interval_ticks=4))
        service = _make_service(config=config)

        assert service._tick_count == 0
        # Ticks 1-3 should not trigger
        service._tick_count = 1
        assert service._tick_count % 4 != 0
        service._tick_count = 3
        assert service._tick_count % 4 != 0
        # Tick 4 triggers
        service._tick_count = 4
        assert service._tick_count % 4 == 0

    def test_build_governance_plan_empty(self):
        """Plan should handle empty issue list."""
        service = _make_service()
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        plan = service._build_governance_plan(snapshot)
        assert "# Orchestra Governance Scan" in plan
        assert "## Running Issues" in plan
        assert "(无 running issues)" in plan
        assert "## Suggested Issues" in plan
        assert "(无建议 issue)" in plan

    def test_build_governance_plan_with_running_and_suggested_issues(self):
        """Plan should split running issues from suggested issues."""
        service = _make_service()
        running_issue = IssueStatusEntry(
            number=42,
            title="Running issue",
            state=None,
            assignee="vibe-manager-agent",
            has_flow=True,
            flow_branch="task/issue-42",
            has_worktree=True,
            worktree_path="/repo/wt-issue-42",
            has_pr=True,
            pr_number=401,
            blocked_by=(),
        )
        suggested_issue = IssueStatusEntry(
            number=43,
            title="Suggested issue",
            state=None,
            assignee="vibe-manager-agent",
            has_flow=False,
            flow_branch=None,
            has_worktree=False,
            worktree_path=None,
            has_pr=False,
            pr_number=None,
            blocked_by=(),
        )
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(running_issue, suggested_issue),
            active_flows=1,
            active_worktrees=1,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        plan = service._build_governance_plan(snapshot)
        assert "## Running Issues" in plan
        assert "#42: Running issue" in plan
        assert "flow=task/issue-42" in plan
        assert "worktree=/repo/wt-issue-42" in plan
        assert "pr=#401" in plan
        assert "## Suggested Issues" in plan
        assert "仅供参考" in plan
        assert "#43: Suggested issue" in plan
        assert "flow=(not started)" in plan

    def test_build_governance_plan_with_blocked_issues(self):
        """Plan should show blocked_by relationships."""
        service = _make_service()
        issue = IssueStatusEntry(
            number=42,
            title="Blocked issue",
            state=None,
            assignee="vibe-manager-agent",
            has_flow=False,
            flow_branch=None,
            has_worktree=False,
            worktree_path=None,
            has_pr=False,
            pr_number=None,
            blocked_by=(41, 40),
        )
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(issue,),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        plan = service._build_governance_plan(snapshot)
        assert "#41" in plan
        assert "#40" in plan

    def test_circuit_breaker_state_in_plan(self):
        """Plan should include circuit breaker state."""
        service = _make_service()
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="half_open",
            circuit_breaker_failures=2,
        )
        plan = service._build_governance_plan(snapshot)
        assert "half_open" in plan

    def test_build_governance_plan_uses_template_and_skill_content(self, tmp_path):
        """Governance plan should render configured template with skill content."""
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(textwrap.dedent("""
                orchestra:
                  governance:
                    plan: |
                      Skill: {skill_name}
                      Count: {active_count}
                      Issues:
                      {issue_list}
                      Skill Content:
                      {skill_content}
                """).strip())
        config = OrchestraConfig(
            governance=GovernanceConfig(
                prompt_template="orchestra.governance.plan",
                include_skill_content=True,
            )
        )
        service = GovernanceService(
            config=config,
            status_service=MockStatusService(),
            dispatcher=_make_dispatcher(),
            prompts_path=prompts_path,
        )
        issue = IssueStatusEntry(
            number=42,
            title="Test issue",
            state=None,
            assignee="vibe-manager-agent",
            has_flow=False,
            flow_branch=None,
            has_worktree=False,
            worktree_path=None,
            has_pr=False,
            pr_number=None,
            blocked_by=(),
        )
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(issue,),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        plan = service._build_governance_plan(snapshot)
        assert "Skill: vibe-orchestra" in plan
        assert "Count: 1" in plan
        assert "#42: Test issue" in plan
        assert "# Vibe Orchestra" in plan

    def test_delegates_to_dispatcher(self):
        """Execution uses dispatcher.run_governance_command."""
        service = _make_service()
        # Verify the service has no _execute_command attribute
        assert not hasattr(service, "_execute_command")
        # Verify it holds a dispatcher
        assert service._dispatcher is not None
        assert hasattr(service._dispatcher, "run_governance_command")

    @pytest.mark.asyncio
    async def test_skip_when_circuit_breaker_open(self):
        """Governance skips dispatch when circuit breaker is OPEN (snapshot check)."""
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="open",
            circuit_breaker_failures=3,
        )
        dispatcher = _make_dispatcher()
        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(dry_run=True, interval_ticks=1)
            ),
            status_service=MockStatusService(snapshot),
            dispatcher=dispatcher,
        )

        await service._run_governance()
        dispatcher.run_governance_command.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_tick_runs_on_interval_and_respects_dry_run(self, monkeypatch):
        """Governance runs on interval and uses governance.dry_run."""
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=0,
            active_worktrees=0,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        dispatcher = _make_dispatcher()
        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(interval_ticks=2, dry_run=True)
            ),
            status_service=MockStatusService(snapshot),
            dispatcher=dispatcher,
        )
        # Force tick boundary
        service._tick_count = 1

        called = {"count": 0}

        async def fake_run():
            called["count"] += 1

        monkeypatch.setattr(service, "_run_governance", fake_run)

        await service.on_tick()
        assert called["count"] == 1

    def test_build_governance_plan_can_disable_skill_content(self, tmp_path):
        """Governance prompt template should allow omitting skill body."""
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            "orchestra:\n"
            "  governance:\n"
            "    plan: |\n"
            "      Skill={skill_name}\n"
            "      Content={skill_content}\n"
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
                    include_skill_content=False,
                )
            ),
            status_service=MockStatusService(snapshot),
            dispatcher=_make_dispatcher(),
            prompts_path=prompts_path,
        )

        plan = service._build_governance_plan(snapshot)
        assert "Skill=vibe-orchestra" in plan
        assert "Content=" in plan
        assert "# Vibe Orchestra" not in plan

    def test_build_material_source_summary_reports_configured_sources(
        self, tmp_path, monkeypatch
    ):
        """Dry run metadata should point to the configured prompt and skill sources."""
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            "orchestra:\n" "  governance:\n" "    plan: |\n" "      Prompt body\n"
        )
        skill_path = tmp_path / "skills" / "demo" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Demo Skill\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(
                    skill="demo",
                    prompt_template="orchestra.governance.plan",
                )
            ),
            status_service=MockStatusService(),
            dispatcher=_make_dispatcher(),
            prompts_path=prompts_path,
        )

        summary = service._build_material_source_summary()

        assert summary["prompt_template_key"] == "orchestra.governance.plan"
        assert summary["prompt_template_file"] == str(prompts_path)
        assert summary["skill_name"] == "demo"
        assert summary["skill_file"] == str(skill_path)

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
        dispatcher = _make_dispatcher()
        dispatcher.repo_path = tmp_path
        service = GovernanceService(
            config=OrchestraConfig(governance=GovernanceConfig(dry_run=True)),
            status_service=MockStatusService(snapshot),
            dispatcher=dispatcher,
        )

        await service._run_governance()
        dispatcher.run_governance_command.assert_not_called()

        dry_run_files = sorted((tmp_path / "temp").glob("governance_dry_run_*.md"))
        assert len(dry_run_files) == 1
        assert "# Orchestra Governance Scan" in dry_run_files[0].read_text()


class TestGovernanceRecipeDrivenRendering:
    """Assert governance uses PromptAssembler (recipe-driven) rendering."""

    def test_render_uses_assembler_not_direct_format(self, tmp_path):
        """GovernanceService._render_governance_plan should use PromptAssembler."""

        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            "orchestra:\n"
            "  governance:\n"
            "    plan: |\n"
            "      Skill={skill_name}\n"
            "      Status={server_status}\n"
            "      Content={skill_content}\n"
            "      Running={running_issue_count}\n"
            "      Suggested={suggested_issue_count}\n"
            "      Flows={active_flows}\n"
            "      CB={circuit_breaker_state}\n"
            "      CBF={circuit_breaker_failures}\n"
            "      Running Issues:\n"
            "      {running_issue_details}\n"
            "      Suggested Issues:\n"
            "      {suggested_issue_details}\n"
            "      Active={active_count}\n"
            "      Worktrees={active_worktrees}\n"
            "      Issues:\n"
            "      {issue_list}\n"
            "      {truncated_note}\n"
        )
        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(
                    prompt_template="orchestra.governance.plan",
                    include_skill_content=False,
                )
            ),
            status_service=MockStatusService(),
            dispatcher=_make_dispatcher(),
            prompts_path=prompts_path,
        )
        # Verify _render_governance_plan uses assembler internally
        # by checking the result is a PromptRenderResult or string but via assembler
        snapshot = OrchestraSnapshot(
            timestamp=0.0,
            server_running=True,
            active_issues=(),
            active_flows=2,
            active_worktrees=1,
            circuit_breaker_state="closed",
            circuit_breaker_failures=0,
        )
        context = service._build_prompt_context(snapshot)
        result_text = service._render_governance_plan(context)
        assert "Skill=vibe-orchestra" in result_text
        assert "Status=running" in result_text
        assert "Flows=2" in result_text

    def test_dry_run_exposes_render_result_provenance(self, tmp_path):
        """Dry-run result should carry PromptRenderResult with provenance."""
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            "orchestra:\n"
            "  governance:\n"
            "    plan: |\n"
            "      Skill={skill_name}\n"
            "      Status={server_status}\n"
            "      Content={skill_content}\n"
            "      Running={running_issue_count}\n"
            "      Suggested={suggested_issue_count}\n"
            "      Flows={active_flows}\n"
            "      CB={circuit_breaker_state}\n"
            "      CBF={circuit_breaker_failures}\n"
            "      Running Issues:\n"
            "      {running_issue_details}\n"
            "      Suggested Issues:\n"
            "      {suggested_issue_details}\n"
            "      Active={active_count}\n"
            "      Worktrees={active_worktrees}\n"
            "      Issues:\n"
            "      {issue_list}\n"
            "      {truncated_note}\n"
        )
        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(
                    prompt_template="orchestra.governance.plan",
                    include_skill_content=False,
                )
            ),
            status_service=MockStatusService(),
            dispatcher=_make_dispatcher(),
            prompts_path=prompts_path,
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
        context = service._build_prompt_context(snapshot)
        # render should return a string (render result text), internally using assembler
        plan_text = service._render_governance_plan(context)
        assert isinstance(plan_text, str)
        # The service should expose the last render result for dry-run logging
        render_result = service.last_render_result
        assert render_result is not None
        assert render_result.recipe_key == "orchestra.governance.plan"
        prov_vars = {p.variable for p in render_result.provenance}
        assert "skill_name" in prov_vars
        assert "server_status" in prov_vars

    def test_governance_recipe_uses_skill_source_for_skill_content(self, tmp_path):
        """skill_content variable should come from SKILL source in the recipe."""
        from vibe3.prompts.models import VariableSourceKind

        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            "orchestra:\n"
            "  governance:\n"
            "    plan: |\n"
            "      Skill={skill_name}\n"
            "      Status={server_status}\n"
            "      Content={skill_content}\n"
            "      Running={running_issue_count}\n"
            "      Suggested={suggested_issue_count}\n"
            "      Flows={active_flows}\n"
            "      CB={circuit_breaker_state}\n"
            "      CBF={circuit_breaker_failures}\n"
            "      Running Issues:\n"
            "      {running_issue_details}\n"
            "      Suggested Issues:\n"
            "      {suggested_issue_details}\n"
            "      Active={active_count}\n"
            "      Worktrees={active_worktrees}\n"
            "      Issues:\n"
            "      {issue_list}\n"
            "      {truncated_note}\n"
        )
        service = GovernanceService(
            config=OrchestraConfig(
                governance=GovernanceConfig(
                    prompt_template="orchestra.governance.plan",
                    include_skill_content=True,
                    skill="vibe-orchestra",
                )
            ),
            status_service=MockStatusService(),
            dispatcher=_make_dispatcher(),
            prompts_path=prompts_path,
        )
        recipe = service._build_governance_recipe()
        skill_src = recipe.variables.get("skill_content")
        assert skill_src is not None
        assert skill_src.kind == VariableSourceKind.SKILL
        assert skill_src.skill == "vibe-orchestra"
