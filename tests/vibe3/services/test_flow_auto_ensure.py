"""Tests for flow auto-ensure functionality."""

from vibe3.clients import SQLiteClient
from vibe3.services.flow_service import FlowService


class TestEnsureFlowForBranch:
    """Test ensure_flow_for_branch functionality."""

    def test_ensure_flow_creates_if_missing(self, tmp_path):
        """Should create flow automatically if not exists."""
        # ARRANGE: Mock branch, no existing flow
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)
        branch = "task/my-feature"

        # ACT: ensure_flow_for_branch
        flow = service.ensure_flow_for_branch(branch)

        # ASSERT: flow created with branch as primary key
        assert flow.branch == branch
        assert flow.flow_slug == "my_feature"  # Derived from branch
        assert flow.flow_status == "active"

        # Verify it's persisted
        retrieved = service.get_flow_status(branch)
        assert retrieved is not None
        assert retrieved.branch == branch

    def test_ensure_flow_returns_existing_if_present(self, tmp_path):
        """Should return existing flow if already present."""
        # ARRANGE: Create existing flow
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)
        branch = "task/my-feature"

        # Create flow first
        existing = service.create_flow(slug="custom_slug", branch=branch)
        assert existing.flow_slug == "custom_slug"

        # ACT: Call ensure_flow_for_branch
        flow = service.ensure_flow_for_branch(branch)

        # ASSERT: Returns existing flow unchanged
        assert flow.branch == branch
        assert flow.flow_slug == "custom_slug"  # Original slug preserved

    def test_ensure_flow_with_custom_slug(self, tmp_path):
        """Should use custom slug if provided."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)
        branch = "task/my-feature"

        # ACT: Call with custom slug
        flow = service.ensure_flow_for_branch(branch, slug="custom_name")

        # ASSERT: Uses custom slug
        assert flow.branch == branch
        assert flow.flow_slug == "custom_name"

    def test_ensure_flow_generates_slug_from_branch(self, tmp_path):
        """Should generate slug from branch name by default."""
        # ARRANGE
        store = SQLiteClient(db_path=tmp_path / "test.db")
        service = FlowService(store=store)

        test_cases = [
            ("task/my-feature", "my_feature"),
            ("task/some-long-name", "some_long_name"),
            ("bugfix/fix-thing", "fix_thing"),
            ("feature/new-api", "new_api"),
        ]

        for branch, expected_slug in test_cases:
            # ACT
            flow = service.ensure_flow_for_branch(branch)

            # ASSERT
            assert flow.flow_slug == expected_slug, f"Branch: {branch}"
