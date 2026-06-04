"""Tests for governance recipe building and prompt rendering."""

import textwrap

import pytest

from vibe3.models.orchestra_config import GovernanceConfig, OrchestraConfig
from vibe3.roles.governance import (
    build_governance_recipe,
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

    def test_supervisor_content_uses_file_source(self):
        config = _make_config()
        recipe = build_governance_recipe(config)
        from vibe3.prompts.models import VariableSourceKind

        src = recipe.variables["supervisor_content"]
        assert src.kind == VariableSourceKind.FILE
        assert src.path == "supervisor/governance/assignee-pool.md"

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

    def test_governance_material_renders_from_global_assets_in_external_repo(
        self, tmp_path, monkeypatch
    ):
        prompts_path = tmp_path / "prompts.yaml"
        prompts_path.write_text(
            textwrap.dedent("""\
                orchestra:
                  governance:
                    plan: |
                      Supervisor={supervisor_name}
                      Material={supervisor_content}
            """),
            encoding="utf-8",
        )
        material_path = tmp_path / "supervisor/governance/roadmap-intake.md"
        material_path.parent.mkdir(parents=True)
        material_path.write_text("GLOBAL ROADMAP INTAKE MATERIAL", encoding="utf-8")
        external_repo = tmp_path / "agent-mesh"
        external_repo.mkdir()
        monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(tmp_path))
        monkeypatch.chdir(external_repo)

        config = _make_config()
        ctx = build_governance_snapshot_context(
            _make_snapshot(),
            config=config,
            tick_count=1,
        )
        result = render_governance_prompt(
            config,
            ctx,
            prompts_path,
            tick_count=0,
            execution_count=1,
        )

        assert (
            "Supervisor=supervisor/governance/roadmap-intake.md" in result.rendered_text
        )
        assert "GLOBAL ROADMAP INTAKE MATERIAL" in result.rendered_text
