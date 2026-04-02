"""Tests for GovernanceService."""

from pathlib import Path
from unittest.mock import MagicMock

from vibe3.orchestra.config import GovernanceConfig, OrchestraConfig
from vibe3.orchestra.services.governance_service import GovernanceService
from vibe3.orchestra.services.status_service import (
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


class TestGovernanceRecipeDrivenRendering:
    """Assert governance uses PromptAssembler (recipe-driven) rendering."""

    def test_render_uses_assembler_not_direct_format(self, tmp_path):
        """GovernanceService._render_governance_plan should use PromptAssembler."""

        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            "orchestra:\n"
            "  governance:\n"
            "    plan: |\n"
            "      Supervisor={supervisor_name}\n"
            "      Status={server_status}\n"
            "      Content={supervisor_content}\n"
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
                    include_supervisor_content=False,
                )
            ),
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
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
        assert "Supervisor=supervisor/orchestra.md" in result_text
        assert "Status=running" in result_text
        assert "Flows=2" in result_text

    def test_dry_run_exposes_render_result_provenance(self, tmp_path):
        """Dry-run result should carry PromptRenderResult with provenance."""
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            "orchestra:\n"
            "  governance:\n"
            "    plan: |\n"
            "      Supervisor={supervisor_name}\n"
            "      Status={server_status}\n"
            "      Content={supervisor_content}\n"
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
                    include_supervisor_content=False,
                )
            ),
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
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
        assert "supervisor_name" in prov_vars
        assert "server_status" in prov_vars

    def test_governance_recipe_uses_file_source_for_supervisor_content(self, tmp_path):
        """supervisor_content comes from FILE source (supervisor/) in the recipe."""
        from vibe3.prompts.models import VariableSourceKind

        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            "orchestra:\n"
            "  governance:\n"
            "    plan: |\n"
            "      Supervisor={supervisor_name}\n"
            "      Status={server_status}\n"
            "      Content={supervisor_content}\n"
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
                    include_supervisor_content=True,
                    supervisor_file="supervisor/orchestra.md",
                )
            ),
            status_service=MockStatusService(),
            manager=_make_dispatcher(),
            prompts_path=prompts_path,
        )
        recipe = service._build_governance_recipe()
        supervisor_src = recipe.variables.get("supervisor_content")
        assert supervisor_src is not None
        assert supervisor_src.kind == VariableSourceKind.FILE
        assert supervisor_src.path == "supervisor/orchestra.md"
