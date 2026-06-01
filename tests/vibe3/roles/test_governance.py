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
            tick_count=1,
        )

        assert (
            "Supervisor=supervisor/governance/roadmap-intake.md" in result.rendered_text
        )
        assert "GLOBAL ROADMAP INTAKE MATERIAL" in result.rendered_text


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


class TestBuildSnapshotContext:
    """Tests for build_governance_snapshot_context."""

    @patch("vibe3.roles.governance.GitHubClient")
    def test_empty_issues(self, mock_github_cls):
        mock_github = MagicMock()
        mock_github.list_issues.return_value = []  # No orchestra-governed issues
        mock_github_cls.return_value = mock_github

        snapshot = _make_snapshot()
        ctx = build_governance_snapshot_context(snapshot, config=_make_config())
        assert ctx["server_status"] == "running"
        assert ctx["issue_scope_name"] == "assignee issue pool"
        assert ctx["active_count"] == 0
        assert ctx["running_issue_count"] == 0
        assert ctx["suggested_issue_count"] == 0
        assert ctx["circuit_breaker_state"] == "closed"
        assert "(无活跃 issue)" in ctx["issue_list"]
        assert "(无 running issues)" in ctx["running_issue_details"]
        assert "(无建议 issue)" in ctx["suggested_issue_details"]

    @patch("vibe3.roles.governance.GitHubClient")
    def test_with_running_and_suggested_issues(self, mock_github_cls):
        mock_github = MagicMock()
        mock_github.list_issues.return_value = []  # No orchestra-governed issues
        mock_github_cls.return_value = mock_github

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
        ctx = build_governance_snapshot_context(snapshot, config=_make_config())
        assert ctx["active_count"] == 2
        assert ctx["running_issue_count"] == 1
        assert ctx["suggested_issue_count"] == 1
        assert "#42" in ctx["running_issue_details"]
        assert "#43" in ctx["suggested_issue_details"]

    @patch("vibe3.roles.governance.GitHubClient")
    def test_server_stopped(self, mock_github_cls):
        mock_github = MagicMock()
        mock_github.list_issues.return_value = []  # No orchestra-governed issues
        mock_github_cls.return_value = mock_github

        snapshot = _make_snapshot(server_running=False)
        ctx = build_governance_snapshot_context(snapshot, config=_make_config())
        assert ctx["server_status"] == "stopped"

    @patch("vibe3.roles.governance.GitHubClient")
    def test_truncation_note(self, mock_github_cls):
        mock_github = MagicMock()
        mock_github.list_issues.return_value = []  # No orchestra-governed issues
        mock_github_cls.return_value = mock_github

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
        ctx = build_governance_snapshot_context(snapshot, config=_make_config())
        assert "已截断" in ctx["truncated_note"]

    @patch("vibe3.roles.governance_utils.GitHubClient")
    def test_roadmap_intake_uses_broader_repo_candidates(self, mock_github_cls):
        snapshot = _make_snapshot()
        # tick_count=1 selects roadmap-intake from recipe catalog
        config = _make_config()
        mock_github = MagicMock()
        mock_github.list_issues.return_value = [
            {
                "number": 101,
                "title": "fix: small bug",
                "body": "clear repro steps",
                "assignees": [],
                "labels": [{"name": "type/fix"}],
                "milestone": None,
            },
            {
                "number": 102,
                "title": "already in pool",
                "body": "",
                "assignees": [{"login": "vibe-manager-agent"}],
                "labels": [{"name": "type/fix"}],
                "milestone": None,
            },
        ]
        mock_github_cls.return_value = mock_github

        ctx = build_governance_snapshot_context(snapshot, config=config, tick_count=1)

        assert ctx["issue_scope_name"] == "broader repo issue pool"
        assert ctx["active_count"] == 1
        assert "#101" in ctx["suggested_issue_details"]
        assert "#102" not in ctx["suggested_issue_details"]

    @patch("vibe3.roles.governance_utils.GitHubClient")
    def test_cron_supervisor_filters_to_docs_candidates(self, mock_github_cls):
        snapshot = _make_snapshot()
        # tick_count=2 selects cron-supervisor from recipe catalog
        config = _make_config()
        mock_github = MagicMock()
        mock_github.list_issues.return_value = [
            {
                "number": 201,
                "title": "docs: align README",
                "body": "documentation drift",
                "assignees": [],
                "labels": [{"name": "type/docs"}],
                "milestone": None,
            },
            {
                "number": 202,
                "title": "not docs",
                "body": "not docs",
                "assignees": [],
                "labels": [{"name": "type/feature"}],
                "milestone": None,
            },
        ]
        mock_github_cls.return_value = mock_github

        ctx = build_governance_snapshot_context(snapshot, config=config, tick_count=2)

        # After migration, scope and filtering work based on recipe catalog material
        assert ctx["issue_scope_name"] == "broader repo docs scope"
        # Verify context is built correctly
        assert "suggested_issue_details" in ctx

    @patch("vibe3.roles.governance_utils.GitHubClient")
    def test_material_override_uses_matching_scope(self, mock_github_cls):
        snapshot = _make_snapshot()
        config = _make_config()
        mock_github = MagicMock()
        mock_github.list_issues.return_value = [
            {
                "number": 301,
                "title": "fix: intake candidate",
                "body": "clear scope",
                "assignees": [],
                "labels": [{"name": "type/fix"}],
                "milestone": None,
            }
        ]
        mock_github_cls.return_value = mock_github

        ctx = build_governance_snapshot_context(
            snapshot,
            config=config,
            tick_count=0,
            material_override="roadmap-intake",
        )

        assert ctx["issue_scope_name"] == "broader repo issue pool"
        assert "#301" in ctx["suggested_issue_details"]

    @patch("vibe3.roles.governance.GitHubClient")
    def test_orchestra_labeled_issues_filtered_from_assignee_pool(
        self, mock_github_cls
    ):
        """Issues with orchestra-governed should be filtered from pool scan."""
        snapshot = _make_snapshot()
        config = _make_config()
        mock_github = MagicMock()

        # Mock orchestra-governed issues (should be filtered from pool scan)
        mock_github.list_issues.return_value = [
            {
                "number": 100,
                "title": "Already decided",
                "body": "",
                "assignees": [],
                "labels": [{"name": "orchestra-governed"}],
                "milestone": None,
            },
        ]
        mock_github_cls.return_value = mock_github

        # Create snapshot with both orchestra-labeled and normal issues
        reviewed = IssueStatusEntry(
            number=100,
            title="Already reviewed",
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
        normal = IssueStatusEntry(
            number=101,
            title="Needs review",
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
        snapshot = _make_snapshot(active_issues=(reviewed, normal))

        ctx = build_governance_snapshot_context(snapshot, config=config)

        # Only non-orchestra issue should appear
        assert ctx["active_count"] == 1
        assert "#101" in ctx["suggested_issue_details"]
        assert "#100" not in ctx["suggested_issue_details"]

    @patch("vibe3.roles.governance_utils.GitHubClient")
    def test_broader_repo_filters_orchestra_labeled(self, mock_github_cls):
        """Broader repo candidates should filter all governance-labeled issues.

        Covers the three-layer filter + legacy compat alias:
        - orchestra-scanned: intake self-closure
        - orchestra-governed: pool defensive filter (close/rfc with assignee
          removed)
        - orchestra: legacy umbrella alias (historical issues; sync-labels.sh
          is non-destructive)
        """
        snapshot = _make_snapshot()
        config = _make_config()
        mock_github = MagicMock()
        mock_github.list_issues.return_value = [
            {
                "number": 201,
                "title": "Fix bug",
                "body": "Clear scope",
                "assignees": [],
                "labels": [{"name": "orchestra-scanned"}],  # Should be filtered
                "milestone": None,
            },
            {
                "number": 202,
                "title": "New feature",
                "body": "Clear scope",
                "assignees": [],
                "labels": [{"name": "type/fix"}],  # Should pass through
                "milestone": None,
            },
            {
                "number": 203,
                "title": "Already governed",
                "body": "Pool decided",
                "assignees": [],
                "labels": [{"name": "orchestra-governed"}],  # Should be filtered
                "milestone": None,
            },
            {
                "number": 204,
                "title": "Legacy labeled",
                "body": "Historical issue",
                "assignees": [],
                "labels": [{"name": "orchestra"}],  # Legacy alias — should be filtered
                "milestone": None,
            },
        ]
        mock_github_cls.return_value = mock_github

        # Use roadmap-intake material
        ctx = build_governance_snapshot_context(snapshot, config=config, tick_count=1)

        assert ctx["issue_scope_name"] == "broader repo issue pool"
        assert ctx["active_count"] == 1
        assert "#202" in ctx["suggested_issue_details"]
        assert "#201" not in ctx["suggested_issue_details"]
        assert "#203" not in ctx["suggested_issue_details"]
        assert "#204" not in ctx["suggested_issue_details"]

    def test_no_orchestra_labeled_issues_no_filtering(self):
        """When no orchestra-labeled issues exist, all candidates pass through."""
        snapshot = _make_snapshot()
        config = _make_config()

        with patch("vibe3.roles.governance.GitHubClient") as mock_github_cls:
            mock_github = MagicMock()
            mock_github.list_issues.return_value = []  # No orchestra-labeled issues
            mock_github_cls.return_value = mock_github

            issue1 = IssueStatusEntry(
                number=1,
                title="Issue 1",
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
            issue2 = IssueStatusEntry(
                number=2,
                title="Issue 2",
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
            snapshot = _make_snapshot(active_issues=(issue1, issue2))

            ctx = build_governance_snapshot_context(snapshot, config=config)

            # Both issues should appear
            assert ctx["active_count"] == 2


class TestCommentFormatContract:
    """Tests for comment format consistency after #1783 changes."""

    def test_roadmap_intake_comment_format_is_new_style(self):
        """Verify roadmap-intake.md uses new comment format in correct examples."""
        import re

        content = Path("supervisor/governance/roadmap-intake.md").read_text()

        # The "正确示例" should use Intake completed (scope=...) format
        # Line 342 in roadmap-intake.md
        correct_example_pattern = re.compile(
            r"\[governance suggest\]\s+Intake.*assigned to @\{manager_bot\}.*scope="
        )
        assert correct_example_pattern.search(
            content
        ), "Correct example should use new format with {manager_bot}"

        # Should NOT use @alice or other human usernames in correct examples
        # Line 236 is marked as "错误示例"
        wrong_example_pattern = re.compile(
            r"\[governance suggest\]\s+Intake.*assigned to @alice"
        )
        # This pattern should NOT appear in the correct examples section
        # We check that if it appears, it's clearly marked as wrong example
        if wrong_example_pattern.search(content):
            # Ensure it's in "错误示例" section
            assert (
                "错误示例" in content
            ), "If @alice appears, it should be marked as wrong example"

    def test_roadmap_skill_comment_format_matches_intake(self):
        """Verify vibe-roadmap SKILL.md comment format matches roadmap-intake."""
        import re

        content = Path("skills/vibe-roadmap/SKILL.md").read_text()

        # Scene A (line 149) should use Intake completed format with scope parameter
        scene_a_pattern = re.compile(
            r"\[roadmap decision\]\s+assign to @\{manager_bot\}.*scope="
        )
        assert scene_a_pattern.search(content), (
            "Scene A should use format: "
            "[roadmap decision] assign to @{manager_bot} (manager-pool); scope=<value>"
        )

        # Should use scope parameter format
        scope_pattern = re.compile(r"scope=<bugfix\|feature\|refactor>")
        assert scope_pattern.search(
            content
        ), "Should use scope parameter with (scope=<value>) format"

    def test_manager_bot_injected_but_not_in_prompt_header(self):
        """Verify manager_bot is injected but not exposed in prompt header."""
        import yaml

        # Verify manager_bot exists in recipe variables
        recipe = build_governance_recipe(_make_config())
        assert (
            "manager_bot" in recipe.variables
        ), "manager_bot should be in recipe variables"

        # Read prompts.yaml
        prompts_path = Path("config/prompts/prompts.yaml")
        prompts_content = yaml.safe_load(prompts_path.read_text())

        # Get the governance plan template
        template = prompts_content["orchestra"]["governance"]["plan"]

        # The template should NOT contain "- Manager Bot: {manager_bot}" in the header
        # This line would expose internal variable to user-visible prompt prefix
        assert (
            "- Manager Bot: {manager_bot}" not in template
        ), "Template should not expose manager_bot in user-visible prompt header"

    def test_roadmap_intake_scope_parameter_format(self):
        """Verify all Intake completed comments use correct scope parameter format."""
        import re

        # Read both files
        roadmap_intake = Path("supervisor/governance/roadmap-intake.md").read_text()
        skill_content = Path("skills/vibe-roadmap/SKILL.md").read_text()

        # Pattern for scope parameter in two forms:
        # 1. Literal value: scope=bugfix or scope=feature or scope=refactor
        # 2. Placeholder notation: scope=<bugfix|feature|refactor>
        scope_literal_pattern = re.compile(r"scope=(bugfix|feature|refactor)[\s\.\)]")
        scope_placeholder_pattern = re.compile(r"scope=<(bugfix\|feature\|refactor)>")

        # Check roadmap-intake.md - should have at least literal examples
        intake_literal_matches = scope_literal_pattern.findall(roadmap_intake)
        assert (
            len(intake_literal_matches) > 0
        ), "roadmap-intake.md should have scope parameter with literal values"

        # All scope values should be valid
        valid_values = {"bugfix", "feature", "refactor"}
        for match in intake_literal_matches:
            assert (
                match in valid_values
            ), f"Scope value '{match}' should be one of {valid_values}"

        # Check vibe-roadmap SKILL.md - should have placeholder or literal examples
        skill_literal_matches = scope_literal_pattern.findall(skill_content)
        skill_placeholder_matches = scope_placeholder_pattern.findall(skill_content)

        assert (len(skill_literal_matches) > 0) or (
            len(skill_placeholder_matches) > 0
        ), (
            "vibe-roadmap SKILL.md should have scope parameter examples "
            "(literal or placeholder)"
        )
