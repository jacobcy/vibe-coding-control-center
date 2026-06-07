"""Tests for TaskService branch validation guards."""

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.exceptions import InvalidBranchLinkError
from vibe3.models.orchestra_config import OrchestraConfig
from vibe3.services.task import TaskService


def test_link_issue_rejects_base_branch_main(tmp_path, monkeypatch):
    """link_issue raises InvalidBranchLinkError for base branch 'main'."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/main"),
    )

    with pytest.raises(InvalidBranchLinkError) as exc_info:
        service.link_issue("main", 999, role="task")

    assert exc_info.value.branch == "main"
    assert exc_info.value.issue_number == 999
    assert "Invalid branch 'main'" in str(exc_info.value)
    assert "DELETE FROM flow_issue_links" in str(exc_info.value)


def test_link_issue_rejects_base_branch_master(tmp_path, monkeypatch):
    """link_issue raises InvalidBranchLinkError for base branch 'master'."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/main"),
    )

    with pytest.raises(InvalidBranchLinkError) as exc_info:
        service.link_issue("master", 999, role="task")

    assert exc_info.value.branch == "master"
    assert exc_info.value.issue_number == 999


def test_link_issue_rejects_base_branch_develop(tmp_path, monkeypatch):
    """link_issue raises InvalidBranchLinkError for base branch 'develop'."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/main"),
    )

    with pytest.raises(InvalidBranchLinkError) as exc_info:
        service.link_issue("develop", 999, role="task")

    assert exc_info.value.branch == "develop"
    assert exc_info.value.issue_number == 999


def test_link_issue_rejects_configured_base_branch(tmp_path, monkeypatch):
    """link_issue raises InvalidBranchLinkError for configured scene_base_ref."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/custom-base"),
    )

    with pytest.raises(InvalidBranchLinkError) as exc_info:
        service.link_issue("custom-base", 999, role="task")

    assert exc_info.value.branch == "custom-base"
    assert exc_info.value.issue_number == 999


def test_link_issue_accepts_valid_branch(tmp_path, monkeypatch):
    """link_issue accepts valid task branch."""
    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/main"),
    )

    store.update_flow_state("task/issue-999", flow_slug="issue-999")
    result = service.link_issue("task/issue-999", 999, role="task")

    assert result.branch == "task/issue-999"
    assert result.issue_number == 999
    assert result.issue_role == "task"


def test_link_issue_rejects_custom_protected_branch(tmp_path, monkeypatch):
    """link_issue raises InvalidBranchLinkError for custom protected branch."""
    from vibe3.config.settings import FlowConfig, VibeConfig

    custom_config = VibeConfig(
        flow=FlowConfig(protected_branches=["staging", "production"])
    )
    monkeypatch.setattr(VibeConfig, "get_defaults", lambda: custom_config)

    db_path = tmp_path / "fresh.db"
    store = SQLiteClient(db_path=str(db_path))
    service = TaskService(
        store=store,
        orchestra_config=OrchestraConfig(scene_base_ref="origin/main"),
    )

    with pytest.raises(InvalidBranchLinkError) as exc_info:
        service.link_issue("staging", 999, role="task")

    assert exc_info.value.branch == "staging"
