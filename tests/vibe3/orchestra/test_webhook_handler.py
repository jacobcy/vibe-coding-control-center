"""Tests for webhook handler: signature validation and event parsing."""

import hashlib
import hmac
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.heartbeat import HeartbeatServer
from vibe3.orchestra.webhook_handler import _verify_signature, make_webhook_router


def _make_app(secret: str | None = None) -> tuple[TestClient, HeartbeatServer]:
    config = OrchestraConfig(polling_interval=900)
    heartbeat = HeartbeatServer(config)
    app = FastAPI()
    app.include_router(make_webhook_router(heartbeat, secret))
    return TestClient(app), heartbeat


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# -- _verify_signature --


def test_verify_valid_signature() -> None:
    body = b'{"action":"assigned"}'
    secret = "mysecret"
    sig = _sign(body, secret)
    assert _verify_signature(body, secret, sig) is True


def test_verify_invalid_signature() -> None:
    body = b'{"action":"assigned"}'
    assert _verify_signature(body, "secret", "sha256=bad") is False


# -- /webhook/github --


def test_webhook_no_secret_accepts_any() -> None:
    client, _ = _make_app(secret=None)
    payload = json.dumps({"action": "assigned"}).encode()
    resp = client.post(
        "/webhook/github",
        content=payload,
        headers={"x-github-event": "issues", "content-type": "application/json"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_webhook_with_valid_secret_passes() -> None:
    secret = "topsecret"
    client, _ = _make_app(secret=secret)
    payload = json.dumps({"action": "assigned"}).encode()
    sig = _sign(payload, secret)
    resp = client.post(
        "/webhook/github",
        content=payload,
        headers={
            "x-github-event": "issues",
            "x-hub-signature-256": sig,
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 200


def test_webhook_with_wrong_secret_rejects() -> None:
    client, _ = _make_app(secret="real-secret")
    payload = json.dumps({"action": "assigned"}).encode()
    bad_sig = _sign(payload, "wrong-secret")
    resp = client.post(
        "/webhook/github",
        content=payload,
        headers={
            "x-github-event": "issues",
            "x-hub-signature-256": bad_sig,
            "content-type": "application/json",
        },
    )
    assert resp.status_code == 403


def test_webhook_missing_sig_when_secret_configured() -> None:
    client, _ = _make_app(secret="configured")
    payload = json.dumps({"action": "assigned"}).encode()
    resp = client.post(
        "/webhook/github",
        content=payload,
        headers={"x-github-event": "issues", "content-type": "application/json"},
    )
    assert resp.status_code == 401


def test_health_endpoint() -> None:
    client, _ = _make_app()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "status" in resp.json()


def test_status_endpoint() -> None:
    client, _ = _make_app()
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data
    assert "polling_interval" in data
    assert "polling_enabled" in data
