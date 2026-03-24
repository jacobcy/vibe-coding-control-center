"""Tests for flow_events enhancements: refs, get_events, timeline."""

import tempfile

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.models.flow import FlowEvent
from vibe3.services.flow_service import FlowService


@pytest.fixture
def db():
    return SQLiteClient(db_path=tempfile.mktemp(suffix=".db"))


@pytest.fixture
def service(db):
    return FlowService(store=db)


class TestGetEvents:
    def test_empty_branch(self, db):
        events = db.get_events("no-such-branch")
        assert events == []

    def test_returns_all_events(self, db):
        db.add_event("br", "flow_created", "claude", detail="one")
        db.add_event("br", "pr_created", "claude", detail="two")
        events = db.get_events("br")
        assert len(events) == 2

    def test_filter_by_type(self, db):
        db.add_event("br", "flow_created", "claude")
        db.add_event("br", "handoff_review", "codex")
        db.add_event("br", "pr_created", "claude")
        review_events = db.get_events("br", event_type="handoff_review")
        assert len(review_events) == 1
        assert review_events[0]["event_type"] == "handoff_review"

    def test_limit(self, db):
        for i in range(5):
            db.add_event("br", "flow_created", "claude", detail=str(i))
        events = db.get_events("br", limit=3)
        assert len(events) == 3

    def test_order_desc(self, db):
        db.add_event("br", "first", "claude")
        db.add_event("br", "second", "claude")
        db.add_event("br", "third", "claude")
        events = db.get_events("br")
        assert events[0]["event_type"] == "third"
        assert events[2]["event_type"] == "first"


class TestRefs:
    def test_refs_none(self, db):
        db.add_event("br", "flow_created", "claude")
        events = db.get_events("br")
        assert events[0]["refs"] is None

    def test_refs_stored_and_retrieved(self, db):
        refs = {"files": ["a.py", "b.py"], "ref": "docs/review.md"}
        db.add_event("br", "handoff_review", "codex", refs=refs)
        events = db.get_events("br")
        assert events[0]["refs"] == refs

    def test_refs_in_flow_event_model(self, db):
        refs = {"audit_ref": "docs/review.md"}
        db.add_event("br", "handoff_review", "codex", refs=refs)
        events_data = db.get_events("br")
        event = FlowEvent(**events_data[0])
        assert event.refs == refs


class TestFlowTimeline:
    def test_timeline_with_state_and_events(self, service, db):
        service.create_flow("test-flow", "br")
        db.add_event("br", "pr_created", "claude", detail="Draft PR #1")
        timeline = service.get_flow_timeline("br")
        assert timeline["state"] is not None
        assert timeline["state"].flow_slug == "test-flow"
        assert len(timeline["events"]) == 2

    def test_timeline_no_state(self, service):
        timeline = service.get_flow_timeline("no-such-branch")
        assert timeline["state"] is None
        assert timeline["events"] == []


class TestHandoffEvents:
    def test_filter_handoff_events(self, db):
        db.add_event("br", "flow_created", "claude")
        db.add_event("br", "handoff_review", "codex", detail="OK")
        db.add_event("br", "handoff_plan", "claude", detail="plan done")
        db.add_event("br", "pr_created", "claude")
        events_data = db.get_events("br")
        handoff = [e for e in events_data if e["event_type"].startswith("handoff_")]
        assert len(handoff) == 2
        assert all(e["event_type"].startswith("handoff_") for e in handoff)
