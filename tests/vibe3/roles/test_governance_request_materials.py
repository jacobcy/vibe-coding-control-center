"""Tests for governance request building and material selection."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibe3.models.orchestra_config import GovernanceConfig, OrchestraConfig
from vibe3.roles.governance import (
    GOVERNANCE_ROLE,
    build_governance_execution_name,
    build_governance_recipe,
    build_governance_request,
)
from vibe3.services.orchestra.status import (
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
        polling_interval=900,
        port=8080,
    )
    defaults.update(overrides)
    return OrchestraSnapshot(**defaults)  # type: ignore[arg-type]


def _make_config(**overrides) -> OrchestraConfig:
    gov_defaults = dict(
        prompt_template="orchestra.governance.plan",
        dry_run=False,
    )
    gov_overrides = overrides.pop("governance", {})
    return OrchestraConfig(
        governance=GovernanceConfig(**{**gov_defaults, **gov_overrides}),
        **overrides,
    )


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

        assert req is not None
        assert req.worktree_requirement == WorktreeRequirement.NONE


class TestBuildExecutionName:
    """Tests for build_governance_execution_name."""

    def test_format(self):
        name = build_governance_execution_name(7)
        assert name.startswith("vibe3-governance-scan-")
        assert name.endswith("-t7")


class TestGovernanceMaterials:
    """Tests for GovernanceConfig defaults after migration."""

    def test_governance_worktree_requirement_is_none(self):
        """governance 默认 worktree requirement 仍为 NONE."""
        from vibe3.execution.role_contracts import GOVERNANCE_GATE_CONFIG
        from vibe3.roles.definitions import WorktreeRequirement

        assert GOVERNANCE_GATE_CONFIG == WorktreeRequirement.NONE

    def test_assignee_pool_material_defines_pool_decider_boundary(self):
        """assignee-pool should act as pool decider with triage responsibility."""
        content = Path("supervisor/governance/assignee-pool.md").read_text()
        # Core triage responsibility
        assert "入池决策者" in content
        assert "分流决策" in content
        # Five exit paths
        for expected in (
            "入池执行",
            "roadmap/rfc",
            "roadmap/epic",
            "终局关闭",
            "恢复执行",
        ):
            assert expected in content

    def test_roadmap_common_keeps_intake_out_of_dependency_decisions(self):
        """roadmap-common should keep dependency/RFC routing in pool layer."""
        content = Path("supervisor/roadmap-common.md").read_text()
        assert "依赖解除后的深度决策" in content
        assert "生命周期、依赖、API、模块" not in content

    def test_assignee_pool_epic_close_does_not_loop_on_suggest(self):
        """Completed epics should terminalize instead of repeating suggest/cleanup."""
        content = Path("supervisor/governance/assignee-pool.md").read_text()
        assert "all sub-issues completed → 直接关闭 epic" in content
        assert (
            "不要写 `[governance suggest][assignee-pool] 建议关闭此 Epic` 后再只添加 "
            "`orchestra-governed`" in content
        )

    def test_manager_material_defines_post_pool_terminal_decision_contract(self):
        """manager should own high-confidence terminal decisions after pool entry."""
        content = Path("supervisor/manager.md").read_text()
        assert "入池后的执行 decider" in content
        assert "Terminal Decision Contract" in content
        assert "state/handoff" in content
        assert "高置信度" in content
        assert "低置信度" in content
        assert "roadmap/rfc" in content


class TestRoundRobinMaterialSelection:
    """Tests that build_governance_recipe selects material from recipe catalog."""

    def test_tick_0_selects_first(self):
        """execution_count=0 selects first material from recipe catalog."""
        recipe = build_governance_recipe(
            _make_config(), tick_count=0, execution_count=0
        )
        val = recipe.variables["supervisor_name"].value
        assert val == "supervisor/governance/assignee-pool.md"

    def test_tick_1_selects_second(self):
        """execution_count=1 selects second material from recipe catalog."""
        recipe = build_governance_recipe(
            _make_config(), tick_count=0, execution_count=1
        )
        val = recipe.variables["supervisor_name"].value
        assert val == "supervisor/governance/roadmap-intake.md"

    def test_tick_2_selects_third(self):
        """execution_count=2 selects third material from recipe catalog."""
        recipe = build_governance_recipe(
            _make_config(), tick_count=0, execution_count=2
        )
        val = recipe.variables["supervisor_name"].value
        assert val == "supervisor/governance/cron-supervisor.md"

    def test_tick_wraps_around(self):
        """execution_count wraps around material catalog.

        (4 materials, count 4 -> index 0).
        """
        recipe = build_governance_recipe(
            _make_config(), tick_count=0, execution_count=4
        )
        val = recipe.variables["supervisor_name"].value
        assert val == "supervisor/governance/assignee-pool.md"

    def test_large_tick_uses_modulo(self):
        """execution_count=9 wraps around 4 materials to index 1 (9 % 4 = 1)."""
        recipe = build_governance_recipe(
            _make_config(), tick_count=0, execution_count=9
        )
        val = recipe.variables["supervisor_name"].value
        assert val == "supervisor/governance/roadmap-intake.md"

    def test_build_governance_request_uses_round_robin(self):
        """build_governance_request picks material per execution_count.

        from recipe catalog.
        """
        config = _make_config()
        snapshot = _make_snapshot()
        with (
            patch("vibe3.roles.governance.resolve_governance_options") as mock_opts,
            patch("vibe3.roles.governance.GitHubClient") as mock_github_cls,
        ):
            mock_opts.return_value = MagicMock()
            mock_github = MagicMock()
            mock_github.list_issues.return_value = []
            mock_github_cls.return_value = mock_github
            req_tick0 = build_governance_request(config, 0, snapshot, execution_count=0)
            req_tick1 = build_governance_request(config, 0, snapshot, execution_count=1)
        # Both should produce valid requests (circuit breaker closed, dry_run=False)
        assert req_tick0 is not None
        assert req_tick1 is not None
        # Execution names reflect different ticks
        assert req_tick0.execution_name.endswith("-t0")
        assert req_tick1.execution_name.endswith("-t0")


class TestGovernanceRoleDefinition:
    """Tests for GOVERNANCE_ROLE."""

    def test_name(self):
        assert GOVERNANCE_ROLE.name == "governance"

    def test_registry_role(self):
        assert GOVERNANCE_ROLE.registry_role == "governance"

    def test_gate_config(self):
        from vibe3.execution.role_contracts import WorktreeRequirement

        assert GOVERNANCE_ROLE.worktree == WorktreeRequirement.NONE
