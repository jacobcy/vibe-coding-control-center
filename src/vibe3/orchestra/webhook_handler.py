"""GitHub webhook receiver: signature validation and event parsing."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from loguru import logger

from vibe3.orchestra.event_bus import GitHubEvent

if TYPE_CHECKING:
    from vibe3.orchestra.heartbeat import HeartbeatServer


def _verify_signature(body: bytes, secret: str, header: str) -> bool:
    """Return True if the HMAC-SHA256 signature matches."""
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def make_webhook_router(
    heartbeat: HeartbeatServer,
    webhook_secret: str | None,
) -> APIRouter:
    """Build a FastAPI router with GitHub webhook and health endpoints."""

    router = APIRouter()

    @router.post("/webhook/github")
    async def receive_webhook(
        request: Request,
        x_github_event: str = Header(...),
        x_hub_signature_256: str | None = Header(None),
    ) -> JSONResponse:
        body = await request.body()

        if webhook_secret:
            if not x_hub_signature_256:
                raise HTTPException(status_code=401, detail="Missing webhook signature")
            if not _verify_signature(body, webhook_secret, x_hub_signature_256):
                raise HTTPException(status_code=403, detail="Invalid webhook signature")

        try:
            payload: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc

        action = str(payload.get("action", ""))

        logger.bind(domain="orchestra", action="webhook").info(
            f"Received: {x_github_event}/{action} (source=webhook)"
        )

        event = GitHubEvent(
            event_type=x_github_event,
            action=action,
            payload=payload,
            source="webhook",
        )
        await heartbeat.emit(event)

        return JSONResponse({"status": "accepted", "event": x_github_event})

    @router.get("/health")
    async def health() -> JSONResponse:
        return JSONResponse(
            {
                "status": "ok",
                "services": heartbeat.service_names,
                "queue_size": heartbeat._event_queue.qsize(),
            }
        )

    @router.get("/status")
    async def status() -> JSONResponse:
        return JSONResponse(
            {
                "running": heartbeat._running,
                "services": heartbeat.service_names,
                "polling_interval": heartbeat.config.polling_interval,
                "max_concurrent": heartbeat.config.max_concurrent_flows,
            }
        )

    return router
