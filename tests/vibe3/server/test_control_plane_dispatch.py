"""Tests for control-plane dispatch and jobs endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from vibe3.domain import GovernanceScanStarted
from vibe3.execution.job_monitor_service import JobMonitorSnapshot
from vibe3.models import (
    ControlPlaneEventPublished,
    ExecutorDispatchIntent,
    ManagerDispatchIntent,
    PlannerDispatchIntent,
    ReviewerDispatchIntent,
    SupervisorIssueIdentified,
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


class TestListJobs:
    """Test jobs listing endpoint."""

    def test_returns_jobs_snapshot(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Verify response structure matches /status jobs format."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)

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
