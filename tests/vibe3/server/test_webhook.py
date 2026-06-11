"""Tests for GitHub webhook endpoint."""

import json
import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from vibe3.models.domain_events import (
    WebhookIssueClosed,
    WebhookIssueUpdated,
    WebhookLabelChanged,
    WebhookPRMerged,
    WebhookPRReviewed,
)
from vibe3.server.webhook import _convert_to_event, _verify_signature, router


class TestVerifySignature:
    """Tests for HMAC signature verification."""

    def test_valid_signature_returns_true(self):
        """Valid signature should return True."""
        payload = b'{"test": "data"}'
        secret = "my-secret"
        # Compute expected signature
        import hashlib
        import hmac

        expected_sig = (
            "sha256="
            + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        )

        assert _verify_signature(payload, expected_sig, secret) is True

    def test_invalid_signature_returns_false(self):
        """Invalid signature should return False."""
        payload = b'{"test": "data"}'
        secret = "my-secret"
        signature = "sha256=invalid_hex"

        assert _verify_signature(payload, signature, secret) is False

    def test_missing_sha256_prefix_returns_false(self):
        """Signature without sha256= prefix should return False."""
        payload = b'{"test": "data"}'
        secret = "my-secret"
        signature = "invalid_hex"

        assert _verify_signature(payload, signature, secret) is False


class TestConvertToEvent:
    """Tests for webhook payload to DomainEvent conversion."""

    def test_issues_labeled_creates_webhooklabelchanged(self):
        """issues + labeled action should create WebhookLabelChanged."""
        payload = {
            "action": "labeled",
            "issue": {"number": 123, "updated_at": "2024-01-01T00:00:00Z"},
            "label": {"name": "state/ready"},
            "sender": {"login": "testuser"},
        }

        event = _convert_to_event("issues", payload)

        assert isinstance(event, WebhookLabelChanged)
        assert event.issue_number == 123
        assert event.label == "state/ready"
        assert event.action == "labeled"
        assert event.sender == "testuser"
        assert event.timestamp == "2024-01-01T00:00:00Z"

    def test_issues_unlabeled_creates_webhooklabelchanged(self):
        """issues + unlabeled action should create WebhookLabelChanged."""
        payload = {
            "action": "unlabeled",
            "issue": {"number": 456},
            "label": {"name": "state/in-progress"},
            "sender": {"login": "testuser"},
        }

        event = _convert_to_event("issues", payload)

        assert isinstance(event, WebhookLabelChanged)
        assert event.issue_number == 456
        assert event.label == "state/in-progress"
        assert event.action == "unlabeled"

    def test_issues_opened_creates_webhookissueupdated(self):
        """issues + opened action should create WebhookIssueUpdated."""
        payload = {
            "action": "opened",
            "issue": {"number": 789},
            "sender": {"login": "testuser"},
        }

        event = _convert_to_event("issues", payload)

        assert isinstance(event, WebhookIssueUpdated)
        assert event.issue_number == 789
        assert event.action == "opened"
        assert event.sender == "testuser"

    def test_issues_edited_creates_webhookissueupdated(self):
        """issues + edited action should create WebhookIssueUpdated."""
        payload = {
            "action": "edited",
            "issue": {"number": 999},
            "sender": {"login": "testuser"},
        }

        event = _convert_to_event("issues", payload)

        assert isinstance(event, WebhookIssueUpdated)
        assert event.issue_number == 999
        assert event.action == "edited"

    def test_issues_closed_creates_webhookissueclosed(self):
        """issues + closed action should create WebhookIssueClosed."""
        payload = {
            "action": "closed",
            "issue": {"number": 111},
            "sender": {"login": "testuser"},
        }

        event = _convert_to_event("issues", payload)

        assert isinstance(event, WebhookIssueClosed)
        assert event.issue_number == 111
        assert event.sender == "testuser"

    def test_pull_request_closed_merged_creates_webhookprmerged(self):
        """pull_request + closed + merged=true should create WebhookPRMerged."""
        payload = {
            "action": "closed",
            "pull_request": {
                "number": 222,
                "merged": True,
                "head": {"ref": "feature-branch"},
                "merged_at": "2024-01-01T00:00:00Z",
            },
            "sender": {"login": "testuser"},
        }

        event = _convert_to_event("pull_request", payload)

        assert isinstance(event, WebhookPRMerged)
        assert event.pr_number == 222
        assert event.branch == "feature-branch"
        assert event.sender == "testuser"
        assert event.timestamp == "2024-01-01T00:00:00Z"

    def test_pull_request_closed_not_merged_returns_none(self):
        """pull_request + closed + merged=false should return None."""
        payload = {
            "action": "closed",
            "pull_request": {"number": 333, "merged": False},
        }

        event = _convert_to_event("pull_request", payload)

        assert event is None

    def test_pull_request_review_submitted_creates_webhookprreviewed(self):
        """pull_request_review + submitted should create WebhookPRReviewed."""
        payload = {
            "action": "submitted",
            "pull_request": {"number": 444},
            "review": {
                "user": {"login": "reviewer"},
                "state": "approved",
                "submitted_at": "2024-01-01T00:00:00Z",
            },
            "sender": {"login": "testuser"},
        }

        event = _convert_to_event("pull_request_review", payload)

        assert isinstance(event, WebhookPRReviewed)
        assert event.pr_number == 444
        assert event.reviewer == "reviewer"
        assert event.state == "approved"
        assert event.sender == "testuser"
        assert event.timestamp == "2024-01-01T00:00:00Z"

    def test_unknown_event_type_returns_none(self):
        """Unknown event type should return None."""
        payload = {"action": "something"}

        event = _convert_to_event("unknown_event", payload)

        assert event is None

    def test_malformed_payload_missing_issue_number_returns_none(self):
        """Malformed payload missing issue number should return None."""
        payload = {
            "action": "labeled",
            "issue": {},  # Missing number
            "label": {"name": "test"},
        }

        event = _convert_to_event("issues", payload)

        assert event is None


class TestWebhookEndpoint:
    """Tests for the /webhook/github endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with webhook router."""
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app)

    def test_valid_webhook_with_correct_signature_returns_200(self, client):
        """Valid webhook with correct signature should return 200."""
        payload = {
            "action": "labeled",
            "issue": {"number": 123},
            "label": {"name": "state/ready"},
            "sender": {"login": "testuser"},
        }
        payload_bytes = json.dumps(payload).encode("utf-8")

        # Compute signature
        import hashlib
        import hmac

        secret = "test-secret"
        signature = (
            "sha256="
            + hmac.new(
                secret.encode("utf-8"), payload_bytes, hashlib.sha256
            ).hexdigest()
        )

        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
            with patch("vibe3.models.publish") as mock_publish:
                response = client.post(
                    "/webhook/github",
                    content=payload_bytes,
                    headers={
                        "X-GitHub-Event": "issues",
                        "X-Hub-Signature-256": signature,
                        "Content-Type": "application/json",
                    },
                )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mock_publish.assert_called_once()

    def test_invalid_signature_returns_401(self, client):
        """Invalid signature should return 401."""
        payload = {"action": "labeled", "issue": {"number": 123}}

        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "test-secret"}):
            response = client.post(
                "/webhook/github",
                content=json.dumps(payload).encode("utf-8"),
                headers={
                    "X-GitHub-Event": "issues",
                    "X-Hub-Signature-256": "sha256=invalid",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == 401

    def test_unrecognized_event_type_returns_200(self, client):
        """Unrecognized event type should return 200 (GitHub requires 2xx)."""
        payload = {"action": "something"}

        # Don't set GITHUB_WEBHOOK_SECRET to skip signature verification
        response = client.post(
            "/webhook/github",
            content=json.dumps(payload).encode("utf-8"),
            headers={
                "X-GitHub-Event": "unknown_event",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200

    def test_missing_event_header_returns_200(self, client):
        """Missing X-GitHub-Event header should return 200."""
        payload = {"action": "labeled"}

        # Don't set GITHUB_WEBHOOK_SECRET to skip signature verification
        response = client.post(
            "/webhook/github",
            content=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200

    def test_publish_failure_returns_200(self, client):
        """Publish failure should still return 200 (GitHub requires 2xx)."""
        payload = {
            "action": "labeled",
            "issue": {"number": 123},
            "label": {"name": "state/ready"},
            "sender": {"login": "testuser"},
        }

        with patch("vibe3.models.publish", side_effect=RuntimeError("publish failed")):
            response = client.post(
                "/webhook/github",
                content=json.dumps(payload).encode("utf-8"),
                headers={
                    "X-GitHub-Event": "issues",
                    "Content-Type": "application/json",
                },
            )

        assert response.status_code == 200

    def test_payload_too_large_returns_200(self, client):
        """Oversized payload should return 200 with error message."""
        # Generate a payload larger than MAX_PAYLOAD_BYTES (5 MB)
        large_string = "x" * (6 * 1024 * 1024)
        payload = {"data": large_string}

        response = client.post(
            "/webhook/github",
            content=json.dumps(payload).encode("utf-8"),
            headers={
                "X-GitHub-Event": "issues",
                "Content-Type": "application/json",
            },
        )

        assert response.status_code == 200
        assert response.json()["status"] == "error"


class TestConvertToEventFieldExtraction:
    """Tests for nested field extraction in payload conversion."""

    def test_nested_issue_fields_extracted_correctly(self):
        """Nested fields in issue object should be extracted correctly."""
        payload = {
            "action": "labeled",
            "issue": {
                "number": 123,
                "updated_at": "2024-01-01T00:00:00Z",
                "title": "Test Issue",
            },
            "label": {"name": "state/ready"},
            "sender": {"login": "testuser"},
        }

        event = _convert_to_event("issues", payload)

        assert isinstance(event, WebhookLabelChanged)
        assert event.issue_number == 123
        assert event.timestamp == "2024-01-01T00:00:00Z"

    def test_missing_nested_fields_uses_defaults(self):
        """Missing nested fields should use default values."""
        payload = {
            "action": "labeled",
            "issue": {"number": 123},
            "label": {"name": "state/ready"},
            # Missing sender and timestamp
        }

        event = _convert_to_event("issues", payload)

        assert isinstance(event, WebhookLabelChanged)
        assert event.sender == ""
        assert event.timestamp is None

    def test_missing_pr_nested_fields_uses_defaults(self):
        """Missing nested fields in PR should use defaults."""
        payload = {
            "action": "closed",
            "pull_request": {
                "number": 456,
                "merged": True,
                # Missing head.ref, sender, merged_at
            },
            "sender": {},
        }

        event = _convert_to_event("pull_request", payload)

        assert isinstance(event, WebhookPRMerged)
        assert event.branch == ""
        assert event.sender == ""
        assert event.timestamp is None

    def test_missing_review_nested_fields_uses_defaults(self):
        """Missing nested fields in review should use defaults."""
        payload = {
            "action": "submitted",
            "pull_request": {"number": 789},
            "review": {
                "state": "approved",
                # Missing user.login, submitted_at
            },
            "sender": {},
        }

        event = _convert_to_event("pull_request_review", payload)

        assert isinstance(event, WebhookPRReviewed)
        assert event.reviewer == ""
        assert event.sender == ""
        assert event.timestamp is None
