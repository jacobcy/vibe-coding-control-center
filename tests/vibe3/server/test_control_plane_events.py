"""Tests for control-plane event publishing and listing endpoints."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from vibe3.models import (
    ControlPlaneEventPublished,
    SupervisorIssueIdentified,
    WebhookIssueClosed,
    WebhookIssueUpdated,
    WebhookLabelChanged,
    WebhookPRMerged,
    WebhookPRReviewed,
)
from vibe3.server.control_plane import _idempotency_store, router


@pytest.fixture
def client():
    """Create test client for control-plane router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def clean_idempotency_store():
    """Reset idempotency store before each test."""
    _idempotency_store._keys.clear()
    yield
    _idempotency_store._keys.clear()


class TestPublishEvent:
    """Test event publishing endpoint."""

    def test_webhooklabelchanged_publishes_event(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Valid request publishes and returns 200."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "event_type": "WebhookLabelChanged",
            "payload": {
                "issue_number": 123,
                "label": "test-label",
                "action": "labeled",
                "sender": "test-user",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/events", json=request_data)
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

            # Verify event was published
            assert _mock_publish.call_count == 2  # Event + audit

            # Check first call was WebhookLabelChanged
            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, WebhookLabelChanged)
            assert event.issue_number == 123
            assert event.label == "test-label"

    def test_disallowed_event_type_returns_400(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Non-allowlisted event type rejected."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "event_type": "ManagerDispatchIntent",  # Not in allowlist
            "payload": {
                "issue_number": 123,
                "branch": "test-branch",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        response = client.post("/api/events", json=request_data)
        assert response.status_code == 400
        assert "not in allowlist" in response.json()["detail"]

    def test_audit_event_published(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify ControlPlaneEventPublished appears in event log."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "event_type": "WebhookLabelChanged",
            "payload": {
                "issue_number": 123,
                "label": "test-label",
                "action": "labeled",
                "sender": "test-user",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/events", json=request_data)
            assert response.status_code == 200

            # Check second call was audit event
            second_call = _mock_publish.call_args_list[1]
            audit_event = second_call[0][0]
            assert isinstance(audit_event, ControlPlaneEventPublished)
            assert audit_event.event_type == "WebhookLabelChanged"
            assert audit_event.actor == "test-actor"
            assert audit_event.idempotency_key == "test-key"

    def test_webhookissueupdated_publishes_event(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """WebhookIssueUpdated event publishes correctly."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "event_type": "WebhookIssueUpdated",
            "payload": {
                "issue_number": 123,
                "action": "edited",
                "sender": "test-user",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/events", json=request_data)
            assert response.status_code == 200

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, WebhookIssueUpdated)
            assert event.issue_number == 123
            assert event.action == "edited"

    def test_webhookissueclosed_publishes_event(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """WebhookIssueClosed event publishes correctly."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "event_type": "WebhookIssueClosed",
            "payload": {
                "issue_number": 123,
                "sender": "test-user",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/events", json=request_data)
            assert response.status_code == 200

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, WebhookIssueClosed)
            assert event.issue_number == 123

    def test_supervisor_issue_identified_publishes_event(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """SupervisorIssueIdentified event publishes correctly."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "event_type": "SupervisorIssueIdentified",
            "payload": {
                "issue_number": 123,
                "issue_title": "Test issue",
                "supervisor_file": "test.py",
                "actor": "supervisor",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/events", json=request_data)
            assert response.status_code == 200

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, SupervisorIssueIdentified)
            assert event.issue_number == 123

    def test_webhookprmerged_publishes_event(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """WebhookPRMerged event publishes correctly."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "event_type": "WebhookPRMerged",
            "payload": {
                "pr_number": 456,
                "sender": "test-user",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/events", json=request_data)
            assert response.status_code == 200

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, WebhookPRMerged)
            assert event.pr_number == 456

    def test_webhookprreviewed_publishes_event(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """WebhookPRReviewed event publishes correctly."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "event_type": "WebhookPRReviewed",
            "payload": {
                "pr_number": 789,
                "reviewer": "reviewer-user",
                "state": "approved",
                "sender": "test-user",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/events", json=request_data)
            assert response.status_code == 200

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, WebhookPRReviewed)
            assert event.pr_number == 789
            assert event.reviewer == "reviewer-user"
            assert event.state == "approved"


class TestListEvents:
    """Test events listing endpoint."""

    def test_returns_recent_events(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify events are returned."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        mock_events = [
            {
                "id": 1,
                "branch": "test-branch",
                "event_type": "WebhookLabelChanged",
                "actor": "test-actor",
                "detail": "Test detail",
                "refs": {"issue": 123},
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]

        with patch("vibe3.clients.SQLiteClient.get_events", return_value=mock_events):
            response = client.get("/api/events")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert len(data["events"]) == 1
            assert data["events"][0]["event_type"] == "WebhookLabelChanged"

    def test_filter_by_event_type(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify filtering by event type works at DB level."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        mock_events = [
            {
                "id": 1,
                "branch": "test-branch",
                "event_type": "WebhookLabelChanged",
                "actor": "test-actor",
                "detail": "Test detail",
                "refs": {"issue": 123},
                "created_at": "2024-01-01T00:00:00Z",
            },
        ]

        with patch(
            "vibe3.clients.SQLiteClient.get_events", return_value=mock_events
        ) as mock_get:
            response = client.get("/api/events?event_type=WebhookLabelChanged")
            assert response.status_code == 200
            data = response.json()
            # Should only return the WebhookLabelChanged event
            assert data["count"] == 1
            assert data["events"][0]["event_type"] == "WebhookLabelChanged"
            # Verify event_type was passed to DB-level query
            mock_get.assert_called_once_with(
                limit=50, branch=None, event_type="WebhookLabelChanged"
            )
