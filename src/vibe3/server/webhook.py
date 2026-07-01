"""GitHub webhook endpoint for receiving and processing webhook events.

Receives GitHub webhook events, verifies HMAC-SHA256 signatures, converts
payloads to DomainEvent types, and publishes them via the event bus.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from vibe3.models import (
    WebhookIssueClosed,
    WebhookIssueUpdated,
    WebhookLabelChanged,
    WebhookPRMerged,
    WebhookPRReviewed,
)

if TYPE_CHECKING:
    from vibe3.models import DomainEvent

router = APIRouter(prefix="/webhook", tags=["webhook"])

# 5 MB max — well above typical GitHub webhook payloads (~1 MB for large PRs)
MAX_PAYLOAD_BYTES = 5 * 1024 * 1024


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature of webhook payload.

    Args:
        payload: Raw request body bytes
        signature: X-Hub-Signature-256 header value (format: "sha256=<hex>")
        secret: Webhook secret for HMAC computation

    Returns:
        True if signature matches, False otherwise
    """
    if not signature.startswith("sha256="):
        return False

    expected_sig = signature[7:]  # Remove "sha256=" prefix
    computed_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_sig, computed_sig)


def _convert_to_event(event_type: str, payload: dict) -> DomainEvent | None:
    """Convert GitHub webhook event to DomainEvent.

    Args:
        event_type: X-GitHub-Event header value
        payload: Parsed JSON payload from webhook

    Returns:
        DomainEvent instance or None if event type not handled
    """
    action = payload.get("action", "")

    try:
        if event_type == "issues":
            issue_number = payload.get("issue", {}).get("number")
            if issue_number is None:
                logger.warning("Webhook issues event missing issue number")
                return None

            sender = payload.get("sender", {}).get("login", "")
            timestamp = payload.get("issue", {}).get("updated_at")

            if action in ("labeled", "unlabeled"):
                label = payload.get("label", {}).get("name", "")
                if not label:
                    logger.warning("Webhook label event missing label name")
                    return None

                return WebhookLabelChanged(
                    issue_number=issue_number,
                    label=label,
                    action=action,
                    sender=sender,
                    timestamp=timestamp,
                )

            elif action in ("opened", "edited"):
                return WebhookIssueUpdated(
                    issue_number=issue_number,
                    action=action,
                    sender=sender,
                    timestamp=timestamp,
                )

            elif action == "closed":
                return WebhookIssueClosed(
                    issue_number=issue_number,
                    sender=sender,
                    timestamp=timestamp,
                )

        elif event_type == "pull_request":
            pr_number = payload.get("pull_request", {}).get("number")
            if pr_number is None:
                logger.warning("Webhook pull_request event missing PR number")
                return None

            if action == "closed" and payload.get("pull_request", {}).get(
                "merged", False
            ):
                branch = payload.get("pull_request", {}).get("head", {}).get("ref", "")
                sender = payload.get("sender", {}).get("login", "")
                timestamp = payload.get("pull_request", {}).get("merged_at")

                return WebhookPRMerged(
                    pr_number=pr_number,
                    branch=branch,
                    sender=sender,
                    timestamp=timestamp,
                )

        elif event_type == "pull_request_review":
            pr_number = payload.get("pull_request", {}).get("number")
            if pr_number is None:
                logger.warning("Webhook pull_request_review event missing PR number")
                return None

            if action == "submitted":
                reviewer = payload.get("review", {}).get("user", {}).get("login", "")
                state = payload.get("review", {}).get("state", "")
                sender = payload.get("sender", {}).get("login", "")
                timestamp = payload.get("review", {}).get("submitted_at")

                return WebhookPRReviewed(
                    pr_number=pr_number,
                    reviewer=reviewer,
                    state=state,
                    sender=sender,
                    timestamp=timestamp,
                )

    except Exception as exc:
        logger.exception(f"Failed to convert webhook event to DomainEvent: {exc}")
        return None

    return None


def _format_event_details(event: DomainEvent) -> str:
    """Format webhook event with key fields for observability.

    Uses loguru color markup to highlight key fields:
    - issue_number/PR number: yellow
    - label/reviewer/state: blue
    - action: red
    - sender: green
    - timestamp: dim

    Args:
        event: Domain event to format

    Returns:
        Formatted string with color markup
    """
    if isinstance(event, WebhookLabelChanged):
        return (
            f"WebhookLabelChanged("
            f"issue=<yellow>#{event.issue_number}</yellow>, "
            f"label=<blue>{event.label}</blue>, "
            f"action=<red>{event.action}</red>, "
            f"sender=<green>{event.sender}</green>, "
            f"timestamp=<dim>{event.timestamp or 'N/A'}</dim>)"
        )
    elif isinstance(event, WebhookIssueUpdated):
        return (
            f"WebhookIssueUpdated("
            f"issue=<yellow>#{event.issue_number}</yellow>, "
            f"action=<red>{event.action}</red>, "
            f"sender=<green>{event.sender}</green>, "
            f"timestamp=<dim>{event.timestamp or 'N/A'}</dim>)"
        )
    elif isinstance(event, WebhookPRMerged):
        return (
            f"WebhookPRMerged("
            f"pr=<yellow>#{event.pr_number}</yellow>, "
            f"branch={event.branch}, "
            f"sender=<green>{event.sender}</green>, "
            f"timestamp=<dim>{event.timestamp or 'N/A'}</dim>)"
        )
    elif isinstance(event, WebhookPRReviewed):
        return (
            f"WebhookPRReviewed("
            f"pr=<yellow>#{event.pr_number}</yellow>, "
            f"reviewer=<green>{event.reviewer}</green>, "
            f"state=<blue>{event.state}</blue>, "
            f"sender=<green>{event.sender}</green>, "
            f"timestamp=<dim>{event.timestamp or 'N/A'}</dim>)"
        )
    elif isinstance(event, WebhookIssueClosed):
        return (
            f"WebhookIssueClosed("
            f"issue=<yellow>#{event.issue_number}</yellow>, "
            f"sender=<green>{event.sender}</green>, "
            f"timestamp=<dim>{event.timestamp or 'N/A'}</dim>)"
        )
    else:
        return event.__class__.__name__


@router.post("/github")
async def handle_github_webhook(request: Request) -> dict:
    """Handle GitHub webhook POST request.

    Verifies HMAC signature, converts payload to DomainEvent, and publishes
    to event bus. Always returns 200 for valid requests to prevent GitHub retries.
    """
    event_type = request.headers.get("X-GitHub-Event", "")

    payload_bytes = await request.body()

    if len(payload_bytes) > MAX_PAYLOAD_BYTES:
        logger.warning(
            f"Webhook payload too large: {len(payload_bytes)} bytes "
            f"(max {MAX_PAYLOAD_BYTES})"
        )
        return {"status": "error", "message": "Payload too large"}

    # Verify signature if secret is configured
    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    signature = request.headers.get("X-Hub-Signature-256", "")

    if secret:
        if not signature:
            logger.warning("Webhook missing signature header")
            raise HTTPException(status_code=401, detail="Missing signature")

        if not _verify_signature(payload_bytes, signature, secret):
            logger.warning("Webhook signature verification failed")
            raise HTTPException(status_code=401, detail="Invalid signature")
    # else: secret not set, verification already warned at startup

    # Parse JSON payload
    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        logger.warning(f"Failed to parse webhook payload: {exc}")
        return {"status": "error", "message": "Invalid JSON"}

    # Convert to DomainEvent
    event = _convert_to_event(event_type, payload)

    if event is None:
        logger.debug(f"Unhandled webhook event type: {event_type}")
        return {"status": "ok", "event": event_type}

    # Publish event
    try:
        from vibe3.models import publish

        publish(event)
        event_details = _format_event_details(event)
        logger.bind(domain="webhook").info(f"Published webhook event: {event_details}")

        # Trigger dependency recheck for closed issues (inline call)
        # Inline call chosen over EventPublisher subscribe — manager approved
        # for simpler synchronous handling without event bus overhead
        if isinstance(event, WebhookIssueClosed):
            try:
                from vibe3.clients import (
                    GitHubClient,
                    SQLiteClient,
                    has_merged_pr_for_issue,
                )
                from vibe3.models import IssueResolvedDependency
                from vibe3.services.dispatch import DependencyRecheckService

                # Check if issue had a merged PR
                merged = has_merged_pr_for_issue(event.issue_number)

                # Create IssueResolvedDependency event
                dep_event = IssueResolvedDependency(
                    issue_number=event.issue_number,
                    merged=merged,
                )

                # Inline call to dependency recheck service
                # Note: constructing clients per request is acceptable here
                # as webhook handler is standalone endpoint without injected context
                store = SQLiteClient()
                github_client = GitHubClient()
                service = DependencyRecheckService(
                    store=store, github_client=github_client
                )
                result = service.handle_issue_resolved(dep_event)

                logger.bind(
                    domain="webhook",
                    action="dependency_recheck",
                    issue_number=event.issue_number,
                    merged=merged,
                    dependents_checked=result.dependents_checked,
                    unblocked=result.unblocked,
                ).info("Dependency recheck triggered for closed issue")
            except Exception as exc:
                # Non-critical path - don't block webhook response
                logger.bind(
                    domain="webhook",
                    action="dependency_recheck",
                    issue_number=event.issue_number,
                    error=str(exc),
                ).warning(f"Failed to trigger dependency recheck: {exc}")
    except Exception as exc:
        logger.bind(domain="webhook").exception(
            f"Failed to publish webhook event: {exc}"
        )

    return {"status": "ok", "event": event_type}
