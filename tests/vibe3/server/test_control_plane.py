"""Tests for control-plane API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from vibe3.domain import GovernanceScanStarted
from vibe3.models import (
    ControlPlaneEventPublished,
    ExecutorDispatchIntent,
    ManagerDispatchIntent,
    PlannerDispatchIntent,
    ReviewerDispatchIntent,
    SupervisorIssueIdentified,
    WebhookIssueClosed,
    WebhookIssueUpdated,
    WebhookLabelChanged,
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


class TestAuth:
    """Test authentication behavior."""

    def test_no_token_configured_accepts_request(
        self, clean_idempotency_store, monkeypatch
    ):
        """When VIBE_CONTROL_PLANE_TOKEN unset, request without header succeeds."""
        # Ensure token is not set
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/events")
        assert response.status_code == 200

    def test_token_configured_rejects_missing_header(
        self, clean_idempotency_store, monkeypatch
    ):
        """Returns 403 when token env var set but header missing."""
        # Clean up any existing token first
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)
        # Then set token
        monkeypatch.setenv("VIBE_CONTROL_PLANE_TOKEN", "test-secret")

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/events")
        assert response.status_code == 403
        assert "Invalid control-plane token" in response.json()["detail"]

    def test_token_configured_rejects_wrong_token(
        self, clean_idempotency_store, monkeypatch
    ):
        """Returns 403 for incorrect token."""
        # Clean up any existing token first
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)
        # Then set token
        monkeypatch.setenv("VIBE_CONTROL_PLANE_TOKEN", "test-secret")

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get(
            "/api/events", headers={"X-Control-Plane-Token": "wrong-secret"}
        )
        assert response.status_code == 403
        assert "Invalid control-plane token" in response.json()["detail"]

    def test_token_configured_accepts_correct_token(
        self, clean_idempotency_store, monkeypatch
    ):
        """Returns 200 for correct token."""
        # Clean up any existing token first
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)
        # Then set token
        monkeypatch.setenv("VIBE_CONTROL_PLANE_TOKEN", "test-secret")

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get(
            "/api/events", headers={"X-Control-Plane-Token": "test-secret"}
        )
        assert response.status_code == 200


class TestIdempotency:
    """Test idempotency behavior."""

    def test_duplicate_request_returns_409(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Same idempotency_key returns conflict."""
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
            "idempotency_key": "test-key-123",
        }

        # First request succeeds
        with patch("vibe3.models.publish") as _mock_publish:
            response1 = client.post("/api/events", json=request_data)
            assert response1.status_code == 200
            assert response1.json()["status"] == "ok"

        # Second request with same key returns duplicate
        with patch("vibe3.models.publish") as _mock_publish:
            response2 = client.post("/api/events", json=request_data)
            assert response2.status_code == 200
            assert response2.json()["status"] == "duplicate"

    def test_different_keys_succeed(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Different keys both succeed."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data_1 = {
            "event_type": "WebhookLabelChanged",
            "payload": {
                "issue_number": 123,
                "label": "test-label",
                "action": "labeled",
                "sender": "test-user",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key-1",
        }

        request_data_2 = {
            "event_type": "WebhookLabelChanged",
            "payload": {
                "issue_number": 456,
                "label": "test-label-2",
                "action": "labeled",
                "sender": "test-user",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key-2",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response1 = client.post("/api/events", json=request_data_1)
            assert response1.status_code == 200
            assert response1.json()["status"] == "ok"

            response2 = client.post("/api/events", json=request_data_2)
            assert response2.status_code == 200
            assert response2.json()["status"] == "ok"

    def test_idempotency_applies_across_endpoints(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Same key on different endpoints conflicts."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        event_request = {
            "event_type": "WebhookLabelChanged",
            "payload": {
                "issue_number": 123,
                "label": "test-label",
                "action": "labeled",
                "sender": "test-user",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "shared-key",
        }

        dispatch_request = {
            "issue_number": 456,
            "branch": "test-branch",
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "shared-key",
        }

        # First request succeeds
        with patch("vibe3.models.publish") as _mock_publish:
            response1 = client.post("/api/events", json=event_request)
            assert response1.status_code == 200
            assert response1.json()["status"] == "ok"

        # Second request with same key on different endpoint returns duplicate
        with patch("vibe3.models.publish") as _mock_publish:
            response2 = client.post("/api/dispatch/manager", json=dispatch_request)
            assert response2.status_code == 200
            assert response2.json()["status"] == "duplicate"


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


class TestDispatch:
    """Test dispatch endpoint."""

    def test_dispatch_manager_creates_intent(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify ManagerDispatchIntent is published."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "issue_number": 123,
            "branch": "test-branch",
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/dispatch/manager", json=request_data)
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, ManagerDispatchIntent)
            assert event.issue_number == 123
            assert event.branch == "test-branch"
            assert event.trigger_state == "ready"

    def test_dispatch_plan_creates_intent(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify PlannerDispatchIntent is published."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "issue_number": 123,
            "branch": "test-branch",
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/dispatch/plan", json=request_data)
            assert response.status_code == 200

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, PlannerDispatchIntent)
            assert event.trigger_state == "claimed"

    def test_dispatch_run_creates_intent(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify ExecutorDispatchIntent is published."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "issue_number": 123,
            "branch": "test-branch",
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/dispatch/run", json=request_data)
            assert response.status_code == 200

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, ExecutorDispatchIntent)
            assert event.trigger_state == "in-progress"

    def test_dispatch_review_creates_intent(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify ReviewerDispatchIntent is published."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "issue_number": 123,
            "branch": "test-branch",
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/dispatch/review", json=request_data)
            assert response.status_code == 200

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, ReviewerDispatchIntent)
            assert event.trigger_state == "review"

    def test_dispatch_governance_creates_intent(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify GovernanceScanStarted published."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "issue_number": 0,  # Not used for governance
            "branch": "",  # Not used for governance
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/dispatch/governance", json=request_data)
            assert response.status_code == 200

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, GovernanceScanStarted)
            assert event.tick_count == 0
            assert event.execution_count == 0

    def test_dispatch_supervisor_apply_creates_intent(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify SupervisorIssueIdentified published."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "issue_number": 123,
            "branch": "test-branch",
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/dispatch/supervisor-apply", json=request_data)
            assert response.status_code == 200

            first_call = _mock_publish.call_args_list[0]
            event = first_call[0][0]
            assert isinstance(event, SupervisorIssueIdentified)
            assert event.issue_number == 123
            assert event.issue_title == ""
            assert event.supervisor_file == ""

    def test_invalid_role_returns_400(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Invalid role returns 400."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "issue_number": 123,
            "branch": "test-branch",
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        response = client.post("/api/dispatch/invalid-role", json=request_data)
        assert response.status_code == 400
        assert "Invalid role" in response.json()["detail"]

    def test_audit_event_published_for_dispatch(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify audit event is published for dispatch."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        request_data = {
            "issue_number": 123,
            "branch": "test-branch",
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "test-key",
        }

        with patch("vibe3.models.publish") as _mock_publish:
            response = client.post("/api/dispatch/manager", json=request_data)
            assert response.status_code == 200

            # Check audit event
            second_call = _mock_publish.call_args_list[1]
            audit_event = second_call[0][0]
            assert isinstance(audit_event, ControlPlaneEventPublished)
            assert audit_event.event_type == "ManagerDispatchIntent"


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
        """Verify filtering by event type works."""
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
            {
                "id": 2,
                "branch": "test-branch",
                "event_type": "WebhookIssueUpdated",
                "actor": "test-actor",
                "detail": "Test detail",
                "refs": {"issue": 456},
                "created_at": "2024-01-01T01:00:00Z",
            },
        ]

        with patch("vibe3.clients.SQLiteClient.get_events", return_value=mock_events):
            response = client.get("/api/events?event_type=WebhookLabelChanged")
            assert response.status_code == 200
            data = response.json()
            # Should only return the WebhookLabelChanged event
            assert data["count"] == 1
            assert data["events"][0]["event_type"] == "WebhookLabelChanged"


class TestListJobs:
    """Test jobs listing endpoint."""

    def test_returns_jobs_snapshot(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify response structure matches /status jobs format."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

        from dataclasses import dataclass

        from vibe3.execution.job_monitor_service import JobMonitorSnapshot

        @dataclass
        class MockActiveJob:
            actor_id: str
            job_type: str
            status: object
            issue_number: int
            branch: str
            started_at: str | None
            completed_at: str | None
            pid: int | None

        class MockStatus:
            def __init__(self, value: str):
                self._value = value

            @property
            def value(self):
                return self._value

        mock_snapshot = JobMonitorSnapshot(
            active_jobs=(
                MockActiveJob(
                    actor_id="test-actor-1",
                    job_type="manager",
                    status=MockStatus("running"),
                    issue_number=123,
                    branch="test-branch",
                    started_at="2024-01-01T00:00:00Z",
                    completed_at=None,
                    pid=12345,
                ),
            ),
            recent_jobs=(
                MockActiveJob(
                    actor_id="test-actor-2",
                    job_type="planner",
                    status=MockStatus("completed"),
                    issue_number=456,
                    branch="test-branch-2",
                    started_at="2024-01-01T00:00:00Z",
                    completed_at="2024-01-01T01:00:00Z",
                    pid=12346,
                ),
            ),
            running_count=1,
            completed_count=1,
            failed_count=0,
        )

        mock_registry = MagicMock()
        mock_registry.size.return_value = 5

        with patch(
            "vibe3.execution.JobMonitorService.snapshot", return_value=mock_snapshot
        ):
            with patch(
                "vibe3.execution.get_actor_registry", return_value=mock_registry
            ):
                response = client.get("/api/jobs")
                assert response.status_code == 200
                data = response.json()

                # Verify structure
                assert "active" in data
                assert "recent" in data
                assert "summary" in data

                # Verify active jobs
                assert len(data["active"]) == 1
                assert data["active"][0]["actor_id"] == "test-actor-1"
                assert data["active"][0]["job_type"] == "manager"
                assert data["active"][0]["status"] == "running"

                # Verify recent jobs
                assert len(data["recent"]) == 1
                assert data["recent"][0]["status"] == "completed"

                # Verify summary
                assert data["summary"]["active_count"] == 1
                assert data["summary"]["recent_count"] == 1
                assert data["summary"]["running_count"] == 1
                assert data["summary"]["completed_count"] == 1
                assert data["summary"]["registry_size"] == 5
