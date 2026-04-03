"""Tests for main branch guard functionality."""

import pytest

from vibe3.clients import SQLiteClient
from vibe3.config.settings import FlowConfig, VibeConfig
from vibe3.models.flow import MainBranchProtectedError
from vibe3.services.flow_service import FlowService


@pytest.fixture(autouse=True)
def stable_worktree_actor(monkeypatch):
    """Avoid real git identity lookups during flow creation tests."""
    monkeypatch.setattr(
        "vibe3.services.flow_service.SignatureService.get_worktree_actor",
        lambda: "test-actor",
    )
    monkeypatch.setattr(
        "vibe3.services.flow_query_mixin.GitHubClient.get_pr",
        lambda self, pr_number=None, branch=None: None,
    )


class TestMainBranchGuard:
    """Test main branch protection logic."""

    def test_ensure_flow_rejects_main_branch(self, tmp_path):
        """Should reject flow creation on main branch."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)

        # ACT & ASSERT: Should raise MainBranchProtectedError
        with pytest.raises(MainBranchProtectedError) as exc_info:
            service.ensure_flow_for_branch("main")

        assert "protected branch" in str(exc_info.value).lower()
        assert "main" in str(exc_info.value)

    def test_ensure_flow_rejects_master_branch(self, tmp_path):
        """Should reject flow creation on master branch."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)

        # ACT & ASSERT: Should raise MainBranchProtectedError
        with pytest.raises(MainBranchProtectedError) as exc_info:
            service.ensure_flow_for_branch("master")

        assert "protected branch" in str(exc_info.value).lower()
        assert "master" in str(exc_info.value)

    def test_ensure_flow_rejects_develop_branch(self, tmp_path):
        """Should reject flow creation on develop branch."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)

        # ACT & ASSERT: Should raise MainBranchProtectedError
        with pytest.raises(MainBranchProtectedError) as exc_info:
            service.ensure_flow_for_branch("develop")

        assert "protected branch" in str(exc_info.value).lower()
        assert "develop" in str(exc_info.value)

    def test_create_flow_also_rejects_main_branch(self, tmp_path):
        """create_flow should also enforce main branch guard."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)

        # ACT & ASSERT
        with pytest.raises(MainBranchProtectedError):
            service.create_flow(slug="test", branch="main")

    def test_custom_main_branches_from_config(self, tmp_path):
        """Should honor protected branches from injected config."""
        store = SQLiteClient(db_path=tmp_path / "test.db")
        config = VibeConfig(
            flow=FlowConfig(protected_branches=["production", "staging"])
        )
        service = FlowService(store=store, config=config)

        with pytest.raises(MainBranchProtectedError):
            service.ensure_flow_for_branch("production")

        with pytest.raises(MainBranchProtectedError):
            service.ensure_flow_for_branch("origin/staging")

        flow = service.ensure_flow_for_branch("main")
        assert flow.branch == "main"

    def test_feature_branch_allowed(self, tmp_path):
        """Should allow flow creation on feature branches."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)

        # ACT: Should NOT raise on feature branch
        flow = service.ensure_flow_for_branch("task/some-feature")

        # ASSERT
        assert flow.branch == "task/some-feature"
        assert flow.flow_status == "active"

    def test_ensure_flow_rejects_safe_branch(self, tmp_path):
        """Should reject flow creation on vibe/main-safe/ branches."""
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)

        with pytest.raises(MainBranchProtectedError) as exc_info:
            service.ensure_flow_for_branch("vibe/main-safe/wt-feature-handoff-1a2b3c4d")

        assert "protected branch" in str(exc_info.value).lower()

    def test_ensure_flow_rejects_safe_branch_origin(self, tmp_path):
        """Should reject flow creation on origin/vibe/main-safe/ branches."""
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)

        with pytest.raises(MainBranchProtectedError) as exc_info:
            service.ensure_flow_for_branch(
                "origin/vibe/main-safe/wt-feature-handoff-1a2b3c4d"
            )

        assert "protected branch" in str(exc_info.value).lower()
