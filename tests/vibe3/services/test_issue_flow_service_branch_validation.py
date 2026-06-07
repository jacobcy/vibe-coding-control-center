"""Tests for IssueFlowService branch validation guards."""

import tempfile
from pathlib import Path

import pytest

from vibe3.exceptions import InvalidBranchLinkError
from vibe3.services.issue.flow import IssueFlowService


class TestIssueFlowServiceBranchValidationGuard:
    """Tests for read guard against corrupted branch links."""

    def test_find_active_flow_rejects_main_branch(self) -> None:
        """find_active_flow raises InvalidBranchLinkError when 'main' is linked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store)

            # Insert corrupted branch link (directly into DB to bypass write guard)
            store.update_flow_state("main", flow_slug="main", flow_status="active")
            store.add_issue_link("main", 999, "task")

            with pytest.raises(InvalidBranchLinkError) as exc_info:
                service.find_active_flow(999)

            assert exc_info.value.branch == "main"
            assert exc_info.value.issue_number == 999
            assert "DELETE FROM flow_issue_links" in str(exc_info.value)

    def test_find_active_flow_rejects_master_branch(self) -> None:
        """find_active_flow raises InvalidBranchLinkError when 'master' is linked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store)

            store.update_flow_state("master", flow_slug="master", flow_status="active")
            store.add_issue_link("master", 999, "task")

            with pytest.raises(InvalidBranchLinkError) as exc_info:
                service.find_active_flow(999)

            assert exc_info.value.branch == "master"
            assert exc_info.value.issue_number == 999

    def test_find_active_flow_rejects_develop_branch(self) -> None:
        """find_active_flow raises InvalidBranchLinkError when 'develop' is linked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store)

            store.update_flow_state(
                "develop", flow_slug="develop", flow_status="active"
            )
            store.add_issue_link("develop", 999, "task")

            with pytest.raises(InvalidBranchLinkError) as exc_info:
                service.find_active_flow(999)

            assert exc_info.value.branch == "develop"
            assert exc_info.value.issue_number == 999

    def test_find_active_flow_accepts_valid_task_branch(self) -> None:
        """find_active_flow accepts valid task branch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store)

            store.update_flow_state(
                "task/issue-999", flow_slug="issue-999", flow_status="active"
            )
            store.add_issue_link("task/issue-999", 999, "task")

            result = service.find_active_flow(999)
            assert result is not None
            assert result["branch"] == "task/issue-999"

    def test_find_active_flow_rejects_custom_protected_branch(
        self, monkeypatch
    ) -> None:
        """find_active_flow rejects custom protected branch from config."""
        from vibe3.config.settings import FlowConfig, VibeConfig

        custom_config = VibeConfig(flow=FlowConfig(protected_branches=["staging"]))
        monkeypatch.setattr(VibeConfig, "get_defaults", lambda: custom_config)

        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store)

            store.update_flow_state(
                "staging", flow_slug="staging", flow_status="active"
            )
            store.add_issue_link("staging", 999, "task")

            with pytest.raises(InvalidBranchLinkError) as exc_info:
                service.find_active_flow(999)

            assert exc_info.value.branch == "staging"

    def test_find_active_flow_rejects_scene_base_ref(self, monkeypatch) -> None:
        """find_active_flow rejects branch matching scene_base_ref from config."""
        from unittest.mock import MagicMock

        from vibe3.models.orchestra_config import OrchestraConfig

        mock_config = MagicMock(spec=OrchestraConfig)
        mock_config.scene_base_ref = "origin/custom-base"

        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store, config=mock_config)

            store.update_flow_state(
                "custom-base", flow_slug="custom-base", flow_status="active"
            )
            store.add_issue_link("custom-base", 999, "task")

            with pytest.raises(InvalidBranchLinkError) as exc_info:
                service.find_active_flow(999)

            assert exc_info.value.branch == "custom-base"
            assert exc_info.value.issue_number == 999

    def test_find_active_flow_strips_origin_prefix_from_scene_base_ref(
        self, monkeypatch
    ) -> None:
        """find_active_flow strips 'origin/' prefix from scene_base_ref.

        Tests comparison after stripping the prefix.
        """
        from unittest.mock import MagicMock

        from vibe3.models.orchestra_config import OrchestraConfig

        mock_config = MagicMock(spec=OrchestraConfig)
        mock_config.scene_base_ref = "origin/custom-base"

        with tempfile.TemporaryDirectory() as tmpdir:
            from vibe3.clients.sqlite_client import SQLiteClient

            db_path = Path(tmpdir) / "test.db"
            store = SQLiteClient(db_path=str(db_path))
            service = IssueFlowService(store=store, config=mock_config)

            # Insert branch WITHOUT origin/ prefix (as stored in DB)
            store.update_flow_state(
                "custom-base", flow_slug="custom-base", flow_status="active"
            )
            store.add_issue_link("custom-base", 999, "task")

            with pytest.raises(InvalidBranchLinkError) as exc_info:
                service.find_active_flow(999)

            assert exc_info.value.branch == "custom-base"
