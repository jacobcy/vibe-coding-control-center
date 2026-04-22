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
        mock_store.add_event.assert_not_called()
        mock_store.update_flow_state.assert_not_called()


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
        mock_store.add_event.assert_not_called()
        mock_store.update_flow_state.assert_not_called()


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
        mock_store.add_event.assert_not_called()
        mock_store.update_flow_state.assert_not_called()


def test_record_agent_artifact_with_log_path(handoff_service, mock_store):
    """Passive artifact persistence should ignore log-only event metadata."""
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
        artifact_path = handoff_service.record_agent_artifact(record)

        assert artifact_path == Path("run_1.md")
        mock_store.add_event.assert_not_called()
        mock_store.update_flow_state.assert_not_called()


def test_record_plan_reference_does_not_inject_unknown_verdict(
    handoff_service, mock_store
):
    with patch.object(handoff_service.storage, "ensure_current_handoff") as mock_ensure:
        mock_ensure.return_value = Path("current.md")
        with patch.object(handoff_service, "append_current_handoff"):
            handoff_service.record_plan("docs/plans/test-plan.md", actor="planner")

    kwargs = mock_store.add_event.call_args[1]
    assert kwargs["detail"] == "Recorded plan reference: docs/plans/test-plan.md"
    assert "verdict" not in kwargs["refs"]
