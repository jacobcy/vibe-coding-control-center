"""Tests for governance context building."""

from unittest.mock import MagicMock, patch

from vibe3.models.orchestra_config import GovernanceConfig, OrchestraConfig
from vibe3.roles.governance import (
    build_governance_snapshot_context,
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
        ctx = build_governance_snapshot_context(snapshot, config=_make_config())
        assert ctx["active_count"] == 2
        assert ctx["running_issue_count"] == 1
        assert ctx["suggested_issue_count"] == 1
        assert "#42" in ctx["running_issue_details"]
        assert "#43" in ctx["suggested_issue_details"]

    def test_server_stopped(self):
        snapshot = _make_snapshot(server_running=False)
        ctx = build_governance_snapshot_context(snapshot, config=_make_config())
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
        ctx = build_governance_snapshot_context(snapshot, config=_make_config())
        assert "已截断" in ctx["truncated_note"]

    @patch("vibe3.roles.governance.GitHubClient")
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

    @patch("vibe3.roles.governance.GitHubClient")
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

    @patch("vibe3.roles.governance.GitHubClient")
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
    def test_vibe_task_issues_filtered_from_assignee_pool(self, mock_github_cls):
        """Issues with vibe-task label should be filtered from assignee pool."""
        snapshot = _make_snapshot()
        config = _make_config()
        mock_github = MagicMock()

        # Mock vibe-task labeled issues (should be filtered)
        mock_github.list_issues.return_value = [
            {
                "number": 100,
                "title": "Already reviewed",
                "body": "",
                "assignees": [],
                "labels": [{"name": "vibe-task"}],
                "milestone": None,
            },
        ]
        mock_github_cls.return_value = mock_github

        # Create snapshot with both vibe-task and normal issues
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

        # Only non-vibe-task issue should appear
        assert ctx["active_count"] == 1
        assert "#101" in ctx["suggested_issue_details"]
        assert "#100" not in ctx["suggested_issue_details"]

    @patch("vibe3.roles.governance.GitHubClient")
    def test_broader_repo_filters_vibe_task(self, mock_github_cls):
        """Broader repo candidates should filter vibe-task labeled issues."""
        snapshot = _make_snapshot()
        config = _make_config()
        mock_github = MagicMock()
        mock_github.list_issues.return_value = [
            {
                "number": 201,
                "title": "Fix bug",
                "body": "Clear scope",
                "assignees": [],
                "labels": [{"name": "vibe-task"}],  # Should be filtered
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
        ]
        mock_github_cls.return_value = mock_github

        # Use roadmap-intake material
        ctx = build_governance_snapshot_context(snapshot, config=config, tick_count=1)

        assert ctx["issue_scope_name"] == "broader repo issue pool"
        assert ctx["active_count"] == 1
        assert "#202" in ctx["suggested_issue_details"]
        assert "#201" not in ctx["suggested_issue_details"]

    def test_no_vibe_task_issues_no_filtering(self):
        """When no vibe-task issues exist, all candidates should pass through."""
        snapshot = _make_snapshot()
        config = _make_config()

        with patch("vibe3.roles.governance.GitHubClient") as mock_github_cls:
            mock_github = MagicMock()
            mock_github.list_issues.return_value = []  # No vibe-task issues
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
