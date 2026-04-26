"""Tests for flow_events enhancements: refs, get_events, timeline."""

import sqlite3
import tempfile

import pytest

from vibe3.clients.sqlite_client import SQLiteClient
from vibe3.clients.sqlite_schema import init_schema
from vibe3.models.flow import FlowEvent
from vibe3.services.flow_service import FlowService


@pytest.fixture(autouse=True)
def stable_worktree_actor(monkeypatch):
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
        db.add_event("br", "audit_recorded", "codex")
        db.add_event("br", "pr_created", "claude")
        review_events = db.get_events("br", event_type="audit_recorded")
        assert len(review_events) == 1
        assert review_events[0]["event_type"] == "audit_recorded"

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
        db.add_event("br", "audit_recorded", "codex", refs=refs)
        events = db.get_events("br")
        assert events[0]["refs"] == refs

    def test_refs_in_flow_event_model(self, db):
        refs = {"audit_ref": "docs/review.md"}
        db.add_event("br", "audit_recorded", "codex", refs=refs)
        events_data = db.get_events("br")
        event = FlowEvent(**events_data[0])
        assert event.refs == refs

    def test_refs_in_flow_event_model_coerces_legacy_scalar_types(self, db):
        refs = {"success": False, "issue": 372, "files": ["a.py", 3]}
        db.add_event("br", "dispatch_result", "codex", refs=refs)
        events_data = db.get_events("br")
        event = FlowEvent(**events_data[0])
        assert event.refs == {
            "success": "False",
            "issue": "372",
            "files": ["a.py", "3"],
        }


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
        db.add_event("br", "handoff_report", "codex", detail="OK")
        db.add_event("br", "handoff_plan", "claude", detail="plan done")
        db.add_event("br", "pr_created", "claude")
        events_data = db.get_events("br")
        handoff = [e for e in events_data if e["event_type"].startswith("handoff_")]
        assert len(handoff) == 2
        assert all(e["event_type"].startswith("handoff_") for e in handoff)

    def test_init_schema_cleans_stale_verdict_lines_for_plan_run_events(self):
        db_path = tempfile.mktemp(suffix=".db")

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "CREATE TABLE flow_events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "branch TEXT NOT NULL,"
                "event_type TEXT NOT NULL,"
                "actor TEXT NOT NULL,"
                "detail TEXT,"
                "created_at TEXT NOT NULL"
                ")"
            )
            cursor.execute(
                "CREATE TABLE flow_state ("
                "branch TEXT PRIMARY KEY,"
                "flow_slug TEXT NOT NULL,"
                "flow_status TEXT NOT NULL DEFAULT 'active',"
                "updated_at TEXT NOT NULL"
                ")"
            )
            cursor.execute(
                "CREATE TABLE flow_issue_links ("
                "branch TEXT NOT NULL,"
                "issue_number INTEGER NOT NULL,"
                "issue_role TEXT NOT NULL,"
                "created_at TEXT NOT NULL,"
                "PRIMARY KEY (branch, issue_number, issue_role)"
                ")"
            )
            cursor.execute(
                "INSERT INTO flow_events "
                "(branch, event_type, actor, detail, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (
                    "task/issue-467",
                    "handoff_plan",
                    "claude/claude-sonnet-4-6",
                    "verdict: UNKNOWN\nRecorded plan reference: "
                    "docs/plans/issue-467.md",
                ),
            )
            cursor.execute(
                "INSERT INTO flow_events "
                "(branch, event_type, actor, detail, created_at) "
                "VALUES (?, ?, ?, ?, datetime('now'))",
                (
                    "task/issue-467",
                    "handoff_audit",
                    "claude/claude-sonnet-4-6",
                    "verdict: UNKNOWN\nRecorded audit reference: "
                    "docs/reports/issue-467.md",
                ),
            )
            conn.commit()

            init_schema(conn)

            rows = conn.execute(
                "SELECT event_type, detail FROM flow_events ORDER BY id"
            ).fetchall()

        assert rows[0][1] == "Recorded plan reference: docs/plans/issue-467.md"
        assert rows[1][1] == (
            "verdict: UNKNOWN\nRecorded audit reference: docs/reports/issue-467.md"
        )
