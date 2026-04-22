"""Tests for record_agent_artifact in HandoffService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.models.handoff import HandoffRecord
from vibe3.models.review_runner import AgentOptions
from vibe3.services.handoff_service import HandoffService


@pytest.fixture
def mock_store():
    return MagicMock(spec=SQLiteClient)


@pytest.fixture
def mock_git_client():
    client = MagicMock(spec=GitClient)
    client.get_current_branch.return_value = "feature/test"
    return client


@pytest.fixture
def handoff_service(mock_store, mock_git_client):
    return HandoffService(store=mock_store, git_client=mock_git_client)


def test_record_agent_artifact_plan(handoff_service, mock_store):
    """Test recording a plan artifact from an agent."""
    options = AgentOptions(backend="openai", model="gpt-4")
    record = HandoffRecord(
        kind="plan",
        content="### Modified Files\n- file1.py\n",
        branch="feature/test",
        options=options,
        metadata={"custom": "value"},
    )

    with patch.object(handoff_service.storage, "create_artifact") as mock_create:
        mock_create.return_value = ("feature/test", Path("plan_1.md"))

        artifact_path = handoff_service.record_agent_artifact(record)

        assert artifact_path == Path("plan_1.md")
        # Verify event was persisted with correct details
        mock_store.add_event.assert_called_once()
        args, kwargs = mock_store.add_event.call_args
        assert args[1] == "handoff_plan"
        assert kwargs["refs"]["backend"] == "openai"
        assert kwargs["refs"]["model"] == "gpt-4"
        assert kwargs["refs"]["custom"] == "value"
        # Plan kind shouldn't have modified_files in refs usually,
        # but our ArtifactParser currently only does it for "run" kind.
        assert "modified_files" not in kwargs["refs"]


def test_record_agent_artifact_run(handoff_service, mock_store):
    """Test recording a run artifact from an agent."""
    options = AgentOptions(backend="anthropic", model="claude-3")
    record = HandoffRecord(
        kind="run",
        content="### Modified Files\n- src/main.py\n- tests/test_main.py\n",
        branch="feature/test",
        options=options,
    )

    with patch.object(handoff_service.storage, "create_artifact") as mock_create:
        mock_create.return_value = ("feature/test", Path("run_1.md"))

        artifact_path = handoff_service.record_agent_artifact(record)

        assert artifact_path == Path("run_1.md")
        mock_store.add_event.assert_called_once()
        args, kwargs = mock_store.add_event.call_args
        assert args[1] == "handoff_report"
        assert kwargs["refs"]["modified_files"] == "src/main.py,tests/test_main.py"
        assert kwargs["refs"]["modified_count"] == "2"


def test_record_agent_artifact_review(handoff_service, mock_store):
    """Test recording a review artifact from an agent."""
    options = AgentOptions(backend="openai", model="gpt-4")
    record = HandoffRecord(
        kind="review",
        content="VERDICT: PASS\nLooks good.",
        branch="feature/test",
        options=options,
        metadata={"comment_count": "5"},
    )

    with patch.object(handoff_service.storage, "create_artifact") as mock_create:
        mock_create.return_value = ("feature/test", Path("review_1.md"))

        artifact_path = handoff_service.record_agent_artifact(record)

        assert artifact_path == Path("review_1.md")
        mock_store.add_event.assert_called_once()
        args, kwargs = mock_store.add_event.call_args
        assert args[1] == "handoff_review"
        assert kwargs["refs"]["verdict"] == "PASS"
        # comment_count should be in detail but NOT in refs if it's handled specifically
        assert "Verdict: PASS, 5 comments" in kwargs["detail"]
        assert "comment_count" not in kwargs["refs"]


def test_record_agent_artifact_with_log_path(handoff_service, mock_store):
    """Test recording an artifact with an external log path."""
    options = AgentOptions(backend="openai", model="gpt-4")
    record = HandoffRecord(
        kind="run",
        content="Done.",
        branch="feature/test",
        options=options,
        log_path="/absolute/path/to/log.txt",
    )

    with patch.object(handoff_service.storage, "create_artifact") as mock_create:
        mock_create.return_value = ("feature/test", Path("run_1.md"))
        with patch.object(handoff_service.storage, "normalize_ref_value") as mock_norm:
            mock_norm.return_value = "temp/log.txt"

            handoff_service.record_agent_artifact(record)

            kwargs = mock_store.add_event.call_args[1]
            assert kwargs["refs"]["log_path"] == "temp/log.txt"
