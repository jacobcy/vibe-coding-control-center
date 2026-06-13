"""Tests for control-plane authentication and idempotency."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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

    def test_empty_idempotency_key_rejected(
        self, client: TestClient, clean_idempotency_store, monkeypatch
    ):
        """Empty string idempotency_key is rejected by Pydantic validation."""
        monkeypatch.delenv("VIBE_CONTROL_PLANE_TOKEN", raising=False)
        request_data = {
            "event_type": "WebhookLabelChanged",
            "payload": {
                "issue_number": 123,
                "label": "x",
                "action": "labeled",
                "sender": "u",
            },
            "actor": "test-actor",
            "source": "test-source",
            "idempotency_key": "",
        }
        response = client.post("/api/events", json=request_data)
        assert response.status_code == 422  # Pydantic validation error
