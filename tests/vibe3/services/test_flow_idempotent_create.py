"""Tests for flow creation idempotency and duplicate dispatch scenarios.

Covers:
- Duplicate create_flow returns existing (idempotency)
- Manager re-trigger (dispatch calls create_flow twice)
- Concurrent existing flow (ensure_flow_for_branch finds existing)
"""

import tempfile

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.services.flow_service import FlowService


@pytest.fixture(autouse=True)
def _stable_actor(monkeypatch):
    """Avoid real git identity lookups during flow creation tests."""
    monkeypatch.setattr(
        "vibe3.services.flow_write_mixin.SignatureService.get_worktree_actor",
        lambda: "test-actor",
    )
    monkeypatch.setattr(
        "vibe3.services.flow_read_mixin.GitHubClient.get_pr",
        lambda self, pr_number=None, branch=None: None,
    )


@pytest.fixture
def db():
    return SQLiteClient(db_path=tempfile.mktemp(suffix=".db"))


@pytest.fixture
def service(db):
    return FlowService(store=db)


class TestDuplicateCreate:
    """create_flow called twice for same branch should return existing."""

    def test_returns_existing_on_duplicate(self, service, db):
        first = service.create_flow("issue-42", "task/issue-42", source="dispatch")
        second = service.create_flow("issue-42", "task/issue-42", source="agent")

        assert first.branch == second.branch
        assert first.flow_slug == second.flow_slug

    def test_no_duplicate_flow_created_event(self, service, db):
        service.create_flow("issue-42", "task/issue-42", source="dispatch")
        service.create_flow("issue-42", "task/issue-42", source="agent")

        events = db.get_events("task/issue-42")
        created_events = [e for e in events if e["event_type"] == "flow_created"]
        assert len(created_events) == 1

    def test_duplicate_preserves_original_state(self, service, db):
        first = service.create_flow("issue-42", "task/issue-42", source="dispatch")
        assert first.flow_slug == "issue-42"

        second = service.create_flow(
            "issue-42-renamed", "task/issue-42", source="agent"
        )
        # Original slug preserved, not overwritten
        assert second.flow_slug == "issue-42"


class TestManagerRetrigger:
    """Simulate dispatch system calling create_flow_for_issue twice."""

    def test_dispatch_then_agent_create_same_branch(self, service, db):
        # First: dispatch creates the flow
        dispatch_flow = service.create_flow(
            "issue-99", "task/issue-99", source="dispatch"
        )
        assert dispatch_flow.flow_slug == "issue-99"

        # Second: agent tries to create the same flow (e.g. via flow update)
        agent_flow = service.create_flow("issue-99", "task/issue-99", source="agent")

        # Same flow returned, no new event
        assert agent_flow.branch == dispatch_flow.branch
        events = db.get_events("task/issue-99")
        created = [e for e in events if e["event_type"] == "flow_created"]
        assert len(created) == 1

    def test_dispatch_creates_branch_then_reactivate(self, service, db):
        # Dispatch creates
        service.create_flow("issue-77", "task/issue-77", source="dispatch")

        # Flow gets marked done (simulating manager completion)
        service.store.update_flow_state("task/issue-77", flow_status="done")

        # Dispatch tries to create again (e.g. handoff re-dispatch)
        service.create_flow("issue-77", "task/issue-77", source="dispatch")
        # Idempotency returns existing (status still "done")
        state = service.store.get_flow_state("task/issue-77")
        assert state["flow_status"] == "done"


class TestConcurrentExistingFlow:
    """ensure_flow_for_branch finds existing flow without side effects."""

    def test_ensure_finds_existing(self, service, db):
        service.create_flow("my-flow", "feature/x", source="dispatch")

        result = service.ensure_flow_for_branch("feature/x", source="cli")
        assert result.flow_slug == "my-flow"

    def test_ensure_no_extra_events(self, service, db):
        service.create_flow("my-flow", "feature/x", source="dispatch")
        service.ensure_flow_for_branch("feature/x", source="cli")

        events = db.get_events("feature/x")
        created = [e for e in events if e["event_type"] == "flow_created"]
        assert len(created) == 1

    def test_source_in_event_refs(self, service, db):
        service.create_flow("my-flow", "feature/x", source="dispatch")

        events = db.get_events("feature/x")
        created = [e for e in events if e["event_type"] == "flow_created"]
        assert created[0]["refs"] == {"source": "dispatch"}
