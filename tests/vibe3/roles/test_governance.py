"""Tests for governance role module functions."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.models.orchestra_config import GovernanceConfig, OrchestraConfig
from vibe3.roles.governance import (
    GOVERNANCE_ROLE,
    build_governance_execution_name,
    build_governance_recipe,
    build_governance_request,
    build_governance_snapshot_context,
    render_governance_prompt,
)
from vibe3.services.orchestra_status_service import (
    IssueStatusEntry,
    OrchestraSnapshot,
)


def _make_snapshot(**overrides: object) -> OrchestraSnapshot:
    defaults: dict[str, object] = dict(
        timestamp=0.0,
        server_running=True,
        active_issues=(),
        active_flows=0,
        active_worktrees=0,
        circuit_breaker_state="closed",
        circuit_breaker_failures=0,
    )
    defaults.update(overrides)
    return OrchestraSnapshot(**defaults)  # type: ignore[arg-type]


def _make_config(**overrides) -> OrchestraConfig:
    gov_defaults = dict(
        prompt_template="orchestra.governance.plan",
        include_supervisor_content=False,
        dry_run=False,
    )
    gov_overrides = overrides.pop("governance", {})
    return OrchestraConfig(
        governance=GovernanceConfig(**{**gov_defaults, **gov_overrides}),
        **overrides,
    )


class TestBuildSnapshotContext:
    """Tests for build_governance_snapshot_context."""

    def test_empty_issues(self):
        snapshot = _make_snapshot()
        ctx = build_governance_snapshot_context(snapshot)
        assert ctx["server_status"] == "running"
        assert ctx["active_count"] == 0
        assert ctx["running_issue_count"] == 0
        assert ctx["suggested_issue_count"] == 0
        assert ctx["circuit_breaker_state"] == "closed"
        assert "(无活跃 issue)" in ctx["issue_list"]
        assert "(无 running issues)" in ctx["running_issue_details"]
        assert "(无建议 issue)" in ctx["suggested_issue_details"]

    def test_with_running_and_suggested_issues(self):
        running = IssueStatusEntry(
            number=42,
            title="Running",
            state=None,
            assignee="vibe-manager-agent",
            has_flow=True,
            flow_branch="task/issue-42",
            has_worktree=True,
            worktree_path="/repo/wt",
            has_pr=True,
            pr_number=401,
            blocked_by=(),
        )
        suggested = IssueStatusEntry(
            number=43,
            title="Suggested",
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
        snapshot = _make_snapshot(
            active_issues=(running, suggested),
            active_flows=1,
            active_worktrees=1,
        )
        ctx = build_governance_snapshot_context(snapshot)
        assert ctx["active_count"] == 2
        assert ctx["running_issue_count"] == 1
        assert ctx["suggested_issue_count"] == 1
        assert "#42" in ctx["running_issue_details"]
        assert "#43" in ctx["suggested_issue_details"]

    def test_server_stopped(self):
        snapshot = _make_snapshot(server_running=False)
        ctx = build_governance_snapshot_context(snapshot)
        assert ctx["server_status"] == "stopped"

    def test_truncation_note(self):
        issues = tuple(
            IssueStatusEntry(
                number=i,
                title=f"Issue {i}",
                state=None,
                assignee="a",
                has_flow=False,
                flow_branch=None,
                has_worktree=False,
                worktree_path=None,
                has_pr=False,
                pr_number=None,
                blocked_by=(),
            )
            for i in range(25)
        )
        snapshot = _make_snapshot(active_issues=issues)
        ctx = build_governance_snapshot_context(snapshot)
        assert "已截断" in ctx["truncated_note"]


class TestBuildGovernanceRecipe:
    """Tests for build_governance_recipe."""

    def test_default_recipe_structure(self):
        config = _make_config()
        recipe = build_governance_recipe(config)
        assert recipe.template_key == "orchestra.governance.plan"
        assert "supervisor_name" in recipe.variables
        assert "server_status" in recipe.variables

    def test_supervisor_content_file_source(self):
        config = _make_config(
            governance=dict(
                include_supervisor_content=True,
                supervisor_file="supervisor/governance/assignee-pool.md",
            ),
        )
        recipe = build_governance_recipe(config)
        from vibe3.prompts.models import VariableSourceKind

        src = recipe.variables["supervisor_content"]
        assert src.kind == VariableSourceKind.FILE
        assert src.path == "supervisor/governance/assignee-pool.md"

    def test_supervisor_content_literal_when_disabled(self):
        config = _make_config(
            governance=dict(include_supervisor_content=False),
        )
        recipe = build_governance_recipe(config)
        src = recipe.variables["supervisor_content"]
        assert src.kind.value == "literal"


class TestRenderGovernancePrompt:
    """Tests for render_governance_prompt."""

    def test_renders_template(self, tmp_path):
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(textwrap.dedent("""\
            orchestra:
              governance:
                plan: |
                  Supervisor={supervisor_name}
                  Status={server_status}
                  Count={active_count}
        """))
        config = _make_config()
        ctx = build_governance_snapshot_context(_make_snapshot())
        result = render_governance_prompt(config, ctx, prompts_path)
        assert (
            "Supervisor=supervisor/governance/assignee-pool.md" in result.rendered_text
        )
        assert "Status=running" in result.rendered_text


class TestBuildGovernanceRequest:
    """Tests for build_governance_request."""

    def test_returns_none_when_circuit_breaker_open(self):
        snapshot = _make_snapshot(circuit_breaker_state="open")
        config = _make_config()
        assert build_governance_request(config, 1, snapshot) is None

    @patch("vibe3.roles.governance._write_dry_run_plan")
    def test_returns_none_when_dry_run(self, mock_write):
        mock_write.return_value = Path("/tmp/dry.md")
        snapshot = _make_snapshot()
        config = _make_config(governance=dict(dry_run=True))
        assert build_governance_request(config, 1, snapshot) is None
        mock_write.assert_called_once()

    @patch("vibe3.roles.governance.resolve_governance_options")
    def test_returns_execution_request(self, mock_opts):
        mock_opts.return_value = MagicMock()
        snapshot = _make_snapshot()
        config = _make_config()
        req = build_governance_request(config, 5, snapshot)
        assert req is not None
        assert req.role == "governance"
        assert req.target_branch == "governance"
        assert req.execution_name.endswith("-t5")
        assert req.mode == "async"

    @patch("vibe3.roles.governance.resolve_governance_options")
    def test_request_has_correct_gates(self, mock_opts):
        mock_opts.return_value = MagicMock()
        snapshot = _make_snapshot()
        config = _make_config()
        req = build_governance_request(config, 1, snapshot)
        from vibe3.execution.role_contracts import WorktreeRequirement

        assert req.worktree_requirement == WorktreeRequirement.NONE


class TestBuildExecutionName:
    """Tests for build_governance_execution_name."""

    def test_format(self):
        name = build_governance_execution_name(7)
        assert name.startswith("vibe3-governance-scan-")
        assert name.endswith("-t7")


class TestGovernanceMaterials:
    """Tests for GovernanceConfig.get_supervisor_materials."""

    def test_get_supervisor_materials_multi(self):
        """governance 在多材料配置下按 tick 轮换."""
        from vibe3.models.orchestra_config import GovernanceConfig

        cfg = GovernanceConfig(
            supervisor_files=[
                "supervisor/governance/assignee-pool.md",
                "supervisor/governance/roadmap-intake.md",
            ]
        )
        materials = cfg.get_supervisor_materials()
        assert materials == [
            "supervisor/governance/assignee-pool.md",
            "supervisor/governance/roadmap-intake.md",
        ]

    def test_get_supervisor_materials_single_fallback(self):
        """旧 supervisor_file 单文件配置仍能工作."""
        from vibe3.models.orchestra_config import GovernanceConfig

        cfg = GovernanceConfig(supervisor_file="supervisor/governance/assignee-pool.md")
        materials = cfg.get_supervisor_materials()
        assert materials == ["supervisor/governance/assignee-pool.md"]

    def test_default_supervisor_file(self):
        """GovernanceConfig 默认 supervisor_file 是 assignee-pool.md."""
        from vibe3.models.orchestra_config import GovernanceConfig

        cfg = GovernanceConfig()
        assert cfg.supervisor_file == "supervisor/governance/assignee-pool.md"

    def test_governance_worktree_requirement_is_none(self):
        """governance 默认 worktree requirement 仍为 NONE."""
        from vibe3.execution.role_contracts import GOVERNANCE_GATE_CONFIG
        from vibe3.roles.definitions import WorktreeRequirement

        assert GOVERNANCE_GATE_CONFIG == WorktreeRequirement.NONE


class TestRoundRobinMaterialSelection:
    """Tests that build_governance_recipe selects material via tick_count % len."""

    def _cfg_with_files(self, files: list[str]) -> OrchestraConfig:
        return _make_config(governance=dict(supervisor_files=files))

    def test_tick_0_selects_first(self):
        files = [
            "supervisor/governance/assignee-pool.md",
            "supervisor/governance/roadmap-intake.md",
            "supervisor/governance/cron-supervisor.md",
        ]
        recipe = build_governance_recipe(self._cfg_with_files(files), tick_count=0)
        assert recipe.variables["supervisor_name"].value == files[0]

    def test_tick_1_selects_second(self):
        files = [
            "supervisor/governance/assignee-pool.md",
            "supervisor/governance/roadmap-intake.md",
            "supervisor/governance/cron-supervisor.md",
        ]
        recipe = build_governance_recipe(self._cfg_with_files(files), tick_count=1)
        assert recipe.variables["supervisor_name"].value == files[1]

    def test_tick_wraps_around(self):
        files = [
            "supervisor/governance/assignee-pool.md",
            "supervisor/governance/roadmap-intake.md",
        ]
        recipe = build_governance_recipe(self._cfg_with_files(files), tick_count=2)
        assert recipe.variables["supervisor_name"].value == files[0]

    def test_large_tick_uses_modulo(self):
        files = [
            "supervisor/governance/assignee-pool.md",
            "supervisor/governance/roadmap-intake.md",
            "supervisor/governance/cron-supervisor.md",
        ]
        recipe = build_governance_recipe(self._cfg_with_files(files), tick_count=7)
        assert recipe.variables["supervisor_name"].value == files[7 % 3]

    def test_single_file_always_selected(self):
        files = ["supervisor/governance/assignee-pool.md"]
        for tick in (0, 1, 99):
            recipe = build_governance_recipe(
                self._cfg_with_files(files), tick_count=tick
            )
            assert recipe.variables["supervisor_name"].value == files[0]

    def test_build_governance_request_uses_round_robin(self):
        """build_governance_request picks the correct material per tick."""
        from unittest.mock import patch

        files = [
            "supervisor/governance/assignee-pool.md",
            "supervisor/governance/roadmap-intake.md",
        ]
        config = _make_config(governance=dict(supervisor_files=files))
        snapshot = _make_snapshot()
        with patch("vibe3.roles.governance.resolve_governance_options") as mock_opts:
            mock_opts.return_value = MagicMock()
            req_tick0 = build_governance_request(config, 0, snapshot)
            req_tick1 = build_governance_request(config, 1, snapshot)
        # Both should produce valid requests (circuit breaker closed, dry_run=False)
        assert req_tick0 is not None
        assert req_tick1 is not None
        # Execution names reflect different ticks
        assert req_tick0.execution_name.endswith("-t0")
        assert req_tick1.execution_name.endswith("-t1")


class TestGovernanceRoleDefinition:
    """Tests for GOVERNANCE_ROLE."""

    def test_name(self):
        assert GOVERNANCE_ROLE.name == "governance"

    def test_registry_role(self):
        assert GOVERNANCE_ROLE.registry_role == "governance"

    def test_gate_config(self):
        from vibe3.execution.role_contracts import WorktreeRequirement

        assert GOVERNANCE_ROLE.worktree == WorktreeRequirement.NONE
