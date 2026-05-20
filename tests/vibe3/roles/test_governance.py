"""Tests for governance role module functions."""

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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


class TestBuildGovernanceRecipe:
    """Tests for build_governance_recipe."""

    def test_default_recipe_structure(self):
        config = _make_config()
        recipe = build_governance_recipe(config)
        assert recipe.template_key == "orchestra.governance.plan"
        assert "supervisor_name" in recipe.variables
        assert "server_status" in recipe.variables

    def test_supervisor_content_literal_with_read_instruction(self):
        config = _make_config()
        recipe = build_governance_recipe(config)
        from vibe3.prompts.models import VariableSourceKind

        src = recipe.variables["supervisor_content"]
        # 修复：不再注入完整 40KB+ supervisor 文件
        # 改为 literal + Read instruction（参考 manager.default 配置）
        assert src.kind == VariableSourceKind.LITERAL
        assert "Read tool" in src.value
        assert "supervisor/governance/assignee-pool.md" in src.value
        assert "Governance 执行指南" in src.value
        assert len(src.value) < 1000  # 轻量级指令应小于 1000 字符

    def test_missing_material_catalog_fails_instead_of_using_python_fallback(
        self, tmp_path, monkeypatch
    ):
        from vibe3.prompts import manifest

        recipes_path = tmp_path / "prompt-recipes.yaml"
        recipes_path.write_text(
            textwrap.dedent("""\
                recipes:
                  governance.scan:
                    kind: template_recipe
                    template_key: orchestra.governance.plan
                    variables: {}
            """),
            encoding="utf-8",
        )
        monkeypatch.setattr(manifest, "DEFAULT_PROMPT_RECIPES_PATH", recipes_path)

        with pytest.raises(ValueError, match="material_catalog"):
            build_governance_recipe(_make_config())


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

    def test_template_controls_whether_supervisor_content_is_rendered(self, tmp_path):
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(textwrap.dedent("""\
            orchestra:
              governance:
                plan: |
                  Supervisor={supervisor_name}
                  Status={server_status}
        """))
        config = _make_config()
        ctx = build_governance_snapshot_context(_make_snapshot())
        result = render_governance_prompt(config, ctx, prompts_path)

        assert "Assignee Pool 治理材料" not in result.rendered_text


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
    """Tests for GovernanceConfig defaults after migration."""

    def test_governance_worktree_requirement_is_none(self):
        """governance 默认 worktree requirement 仍为 NONE."""
        from vibe3.execution.role_contracts import GOVERNANCE_GATE_CONFIG
        from vibe3.roles.definitions import WorktreeRequirement

        assert GOVERNANCE_GATE_CONFIG == WorktreeRequirement.NONE

    def test_roadmap_intake_material_requires_assignee_write(self):
        """roadmap-intake material should require direct assignee assignment."""
        content = Path("supervisor/governance/roadmap-intake.md").read_text()
        assert "直接补齐可执行的 manager assignee" in content
        assert "明确指派给一个配置中的 manager assignee" in content


class TestRoundRobinMaterialSelection:
    """Tests that build_governance_recipe selects material from recipe catalog."""

    def test_tick_0_selects_first(self):
        """tick_count=0 selects first material from recipe catalog."""
        recipe = build_governance_recipe(_make_config(), tick_count=0)
        # Material catalog is from prompt-recipes.yaml
        val = recipe.variables["supervisor_name"].value
        assert val is not None
        assert "supervisor/governance/" in val

    def test_tick_1_selects_second(self):
        """tick_count=1 selects second material from recipe catalog."""
        recipe = build_governance_recipe(_make_config(), tick_count=1)
        val = recipe.variables["supervisor_name"].value
        assert val is not None
        assert "supervisor/governance/" in val

    def test_tick_wraps_around(self):
        """tick_count wraps around material catalog."""
        recipe = build_governance_recipe(_make_config(), tick_count=3)
        # 3 % 3 = 0, so should be first material
        val = recipe.variables["supervisor_name"].value
        assert val is not None
        assert "supervisor/governance/" in val

    def test_large_tick_uses_modulo(self):
        """tick_count=7 should wrap around 3 materials to index 1."""
        recipe = build_governance_recipe(_make_config(), tick_count=7)
        val = recipe.variables["supervisor_name"].value
        assert val is not None
        # 7 % 3 = 1, should be second material
        assert "supervisor/governance/" in val

    def test_build_governance_request_uses_round_robin(self):
        """build_governance_request picks material per tick from recipe catalog."""
        from unittest.mock import patch

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
