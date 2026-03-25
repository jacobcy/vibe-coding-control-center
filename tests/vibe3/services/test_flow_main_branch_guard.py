"""Tests for main branch guard functionality."""

import pytest

from vibe3.clients import SQLiteClient
from vibe3.models.flow import MainBranchProtectedError
from vibe3.services.flow_service import FlowService


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
        """Should read main branches from config."""
        # ARRANGE: Create config with custom main branches

        import yaml

        config_path = tmp_path / "settings.yaml"
        config_data = {"flow": {"protected_branches": ["production", "staging"]}}
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        # TODO: Load config and test
        # For now, this test documents the requirement

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
