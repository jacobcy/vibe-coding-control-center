"""Control-plane API for publishing events and triggering dispatches.

Provides authenticated REST endpoints for:
- Publishing allowlisted domain events
- Triggering role dispatches (manager, plan, run, review, governance, supervisor-apply)
- Querying event history and active jobs

All mutations go through the EventPublisher — the API never calls
roles/execution directly.
"""

from __future__ import annotations

import os
import threading
import time
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from vibe3.models import DomainEvent

router = APIRouter(prefix="/api", tags=["control-plane"])

# =============================================================================
# Pydantic Request/Response Models
# =============================================================================


class EventPublishRequest(BaseModel):
    """Request to publish an allowlisted DomainEvent."""

    event_type: str  # e.g. "WebhookLabelChanged"
    payload: dict[str, Any]  # Fields for the target DomainEvent
    actor: str  # e.g. "dashboard:jacobcy"
    source: str = "api-client"  # e.g. "web-dashboard"
    idempotency_key: str = Field(min_length=1)  # Client-generated unique key


class DispatchRequest(BaseModel):
    """Request to trigger role dispatch."""

    issue_number: int
    branch: str
    actor: str
    source: str = "api-client"
    idempotency_key: str = Field(min_length=1)


class ApiResponse(BaseModel):
    """Standard API response."""

    status: str  # "ok" | "error" | "duplicate"
    detail: str = ""
    idempotency_key: str = ""


class EventEntry(BaseModel):
    """Single event for GET /api/events response."""

    id: int
    branch: str
    event_type: str
    actor: str
    detail: str | None
    refs: dict[str, Any] | None
    created_at: str


class EventsResponse(BaseModel):
    """Response for GET /api/events."""

    events: list[EventEntry]
    count: int


class JobEntry(BaseModel):
    """Single job for GET /api/jobs response."""

    actor_id: str
    job_type: str
    status: str
    issue_number: int
    branch: str
    started_at: str | None
    completed_at: str | None
    pid: int | None


class JobsResponse(BaseModel):
    """Response for GET /api/jobs."""

    active: list[JobEntry]
    recent: list[JobEntry]
    summary: dict[str, Any]


# =============================================================================
# Allowlist of Event Types
# =============================================================================

ALLOWED_EVENT_TYPES = {
    "WebhookLabelChanged",
    "WebhookIssueUpdated",
    "WebhookIssueClosed",
    "WebhookPRMerged",
    "WebhookPRReviewed",
    "SupervisorIssueIdentified",
}

# Dispatch roles to event mapping
DISPATCH_ROLES = {
    "manager",
    "plan",
    "run",
    "review",
    "governance",
    "supervisor-apply",
}

# =============================================================================
# Auth Dependency
# =============================================================================


async def verify_control_plane_token(
    x_control_plane_token: str | None = Header(
        default=None, alias="X-Control-Plane-Token"
    ),
) -> str:
    """Verify control-plane token from header.

    If VIBE_CONTROL_PLANE_TOKEN is not set, allow access (localhost-only convention).
    If set, require exact match in header.

    Returns:
        "authenticated" or "unauth-local"
    """
    token = os.environ.get("VIBE_CONTROL_PLANE_TOKEN")
    if not token:
        return "unauth-local"  # Warning logged at mount time, access allowed

    if x_control_plane_token != token:
        raise HTTPException(status_code=403, detail="Invalid control-plane token")

    return "authenticated"


# =============================================================================
# Idempotency Store
# =============================================================================


class IdempotencyStore:
    """In-memory idempotency key tracker with TTL (default 1 hour)."""

    def __init__(self, ttl_seconds: int = 3600):
        self._keys: dict[str, tuple[float, str]] = {}  # key -> (timestamp, endpoint)
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def check_and_record(self, key: str, endpoint: str) -> bool:
        """Check if key is new and record it.

        Args:
            key: Idempotency key to check
            endpoint: Endpoint name for debugging (e.g., "/api/events")

        Returns:
            True if key is new (should proceed), False if duplicate
        """
        now = time.time()
        with self._lock:
            # Clean expired keys
            expired = [k for k, (t, _) in self._keys.items() if now - t > self._ttl]
            for k in expired:
                del self._keys[k]

            # Check if key exists
            if key in self._keys:
                timestamp, prev_endpoint = self._keys[key]
                logger.bind(domain="control-plane").warning(
                    f"Duplicate idempotency key {key[:16]}... "
                    f"(previously used at {prev_endpoint} {int(now - timestamp)}s ago)"
                )
                return False

            # Record new key
            self._keys[key] = (now, endpoint)
            return True


# Global idempotency store instance
_idempotency_store = IdempotencyStore()


# =============================================================================
# Helper Functions
# =============================================================================


def _construct_event(event_type: str, payload: dict[str, Any]) -> DomainEvent | None:
    """Construct a DomainEvent from event_type and payload.

    Args:
        event_type: Name of the DomainEvent class
        payload: Dict of fields for the event constructor

    Returns:
        DomainEvent instance or None if construction fails
    """
    try:
        # Import event classes dynamically
        if event_type == "WebhookLabelChanged":
            from vibe3.models import WebhookLabelChanged

            issue_number = payload.get("issue_number")
            if issue_number is None:
                logger.error("WebhookLabelChanged missing issue_number")
                return None

            return WebhookLabelChanged(
                issue_number=issue_number,
                label=payload.get("label", ""),
                action=payload.get("action", ""),
                sender=payload.get("sender", ""),
                timestamp=payload.get("timestamp"),
            )

        elif event_type == "WebhookIssueUpdated":
            from vibe3.models import WebhookIssueUpdated

            issue_number = payload.get("issue_number")
            if issue_number is None:
                logger.error("WebhookIssueUpdated missing issue_number")
                return None

            return WebhookIssueUpdated(
                issue_number=issue_number,
                action=payload.get("action", ""),
                sender=payload.get("sender", ""),
                timestamp=payload.get("timestamp"),
            )

        elif event_type == "WebhookIssueClosed":
            from vibe3.models import WebhookIssueClosed

            issue_number = payload.get("issue_number")
            if issue_number is None:
                logger.error("WebhookIssueClosed missing issue_number")
                return None

            return WebhookIssueClosed(
                issue_number=issue_number,
                sender=payload.get("sender", ""),
                timestamp=payload.get("timestamp"),
            )

        elif event_type == "WebhookPRMerged":
            from vibe3.models import WebhookPRMerged

            pr_number = payload.get("pr_number")
            if pr_number is None:
                logger.error("WebhookPRMerged missing pr_number")
                return None

            return WebhookPRMerged(
                pr_number=pr_number,
                sender=payload.get("sender", ""),
                timestamp=payload.get("timestamp"),
            )

        elif event_type == "WebhookPRReviewed":
            from vibe3.models import WebhookPRReviewed

            pr_number = payload.get("pr_number")
            if pr_number is None:
                logger.error("WebhookPRReviewed missing pr_number")
                return None

            return WebhookPRReviewed(
                pr_number=pr_number,
                reviewer=payload.get("reviewer", ""),
                state=payload.get("state", ""),
                sender=payload.get("sender", ""),
                timestamp=payload.get("timestamp"),
            )

        elif event_type == "SupervisorIssueIdentified":
            from vibe3.models import SupervisorIssueIdentified

            issue_number = payload.get("issue_number")
            if issue_number is None:
                logger.error("SupervisorIssueIdentified missing issue_number")
                return None

            return SupervisorIssueIdentified(
                issue_number=issue_number,
                issue_title=payload.get("issue_title", ""),
                supervisor_file=payload.get("supervisor_file", ""),
                actor=payload.get("actor", ""),
            )

        else:
            logger.error(f"Unknown event type: {event_type}")
            return None

    except Exception as exc:
        logger.exception(f"Failed to construct event {event_type}: {exc}")
        return None


def _construct_dispatch_event(
    role: str, issue_number: int, branch: str, actor: str
) -> DomainEvent | None:
    """Construct dispatch intent event for the given role.

    Args:
        role: Role name (manager, plan, run, review, governance, supervisor-apply)
        issue_number: Issue number for the dispatch
        branch: Branch name for the dispatch
        actor: Actor triggering the dispatch

    Returns:
        DomainEvent instance or None if role is invalid
    """
    try:
        if role == "manager":
            from vibe3.models import ManagerDispatchIntent

            return ManagerDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="ready",
                actor=actor,
                tick_id=0,
            )

        elif role == "plan":
            from vibe3.models import PlannerDispatchIntent

            return PlannerDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="claimed",
                actor=actor,
                tick_id=0,
            )

        elif role == "run":
            from vibe3.models import ExecutorDispatchIntent

            return ExecutorDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="in-progress",
                actor=actor,
                tick_id=0,
            )

        elif role == "review":
            from vibe3.models import ReviewerDispatchIntent

            return ReviewerDispatchIntent(
                issue_number=issue_number,
                branch=branch,
                trigger_state="review",
                actor=actor,
                tick_id=0,
            )

        elif role == "governance":
            from vibe3.domain import GovernanceScanStarted

            return GovernanceScanStarted(
                tick_count=0,
                execution_count=0,
                actor=actor,
            )

        elif role == "supervisor-apply":
            from vibe3.models import SupervisorIssueIdentified

            # Note: supervisor-apply creates minimal SupervisorIssueIdentified events
            # with empty issue_title and supervisor_file. Downstream handlers should
            # handle these minimal fields. Log warning for visibility.
            logger.bind(domain="control-plane").warning(
                "Creating SupervisorIssueIdentified with minimal fields "
                "(empty issue_title and supervisor_file)",
                extra={"issue_number": issue_number, "actor": actor},
            )

            return SupervisorIssueIdentified(
                issue_number=issue_number,
                issue_title="",
                supervisor_file="",
                actor=actor,
            )

        else:
            logger.error(f"Unknown dispatch role: {role}")
            return None

    except Exception as exc:
        logger.exception(f"Failed to construct dispatch event for role {role}: {exc}")
        return None


# =============================================================================
# Routes
# =============================================================================


@router.post("/events", response_model=ApiResponse)
async def publish_event(
    request: EventPublishRequest,
    _: str = Depends(verify_control_plane_token),
) -> ApiResponse:
    """Publish an allowlisted domain event.

    Args:
        request: Event publish request with event_type, payload, actor, etc.
        _: Auth dependency (unused return value)

    Returns:
        ApiResponse with status and detail
    """
    # Check idempotency
    if not _idempotency_store.check_and_record(request.idempotency_key, "/api/events"):
        return ApiResponse(
            status="duplicate",
            detail="Request already processed",
            idempotency_key=request.idempotency_key,
        )

    # Validate event type is in allowlist
    if request.event_type not in ALLOWED_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Event type '{request.event_type}' not in allowlist",
        )

    # Construct the target event
    event = _construct_event(request.event_type, request.payload)
    if event is None:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to construct event {request.event_type}",
        )

    # Import publish function
    from vibe3.models import publish

    # Publish the target event
    try:
        publish(event)
        logger.bind(domain="control-plane").info(
            f"Published event {request.event_type} via control-plane API",
            extra={
                "event_type": request.event_type,
                "actor": request.actor,
                "source": request.source,
            },
        )
    except Exception as exc:
        logger.exception(f"Failed to publish event: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish event: {exc}",
        )

    # Publish audit event
    from vibe3.models import ControlPlaneEventPublished

    audit_event = ControlPlaneEventPublished(
        event_type=request.event_type,
        issue_number=request.payload.get("issue_number"),
        actor=request.actor,
        source=request.source,
        idempotency_key=request.idempotency_key,
        detail="Event published via control-plane API",
    )

    try:
        publish(audit_event)
    except Exception as exc:
        # CRITICAL: Audit event publish failure means loss of accountability record.
        # Log with high priority but don't fail the request (per acceptance criteria).
        # TODO: Add monitoring/alerting for audit failures in production.
        logger.bind(domain="control-plane").error(
            f"CRITICAL: Failed to publish audit event for {request.event_type} "
            f"(actor={request.actor}, key={request.idempotency_key[:16]}...). "
            f"Audit trail entry LOST. Error: {exc}"
        )

    return ApiResponse(
        status="ok",
        detail="Event published",
        idempotency_key=request.idempotency_key,
    )


@router.post("/dispatch/{role}", response_model=ApiResponse)
async def trigger_dispatch(
    role: str,
    request: DispatchRequest,
    _: str = Depends(verify_control_plane_token),
) -> ApiResponse:
    """Trigger a role dispatch.

    Args:
        role: Role to dispatch (manager, plan, run, review, governance,
            supervisor-apply)
        request: Dispatch request with issue_number, branch, actor, etc.
        _: Auth dependency (unused return value)

    Returns:
        ApiResponse with status and detail
    """
    # Check idempotency
    if not _idempotency_store.check_and_record(
        request.idempotency_key, f"/api/dispatch/{role}"
    ):
        return ApiResponse(
            status="duplicate",
            detail="Request already processed",
            idempotency_key=request.idempotency_key,
        )

    # Validate role
    if role not in DISPATCH_ROLES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid role '{role}'. "
                f"Must be one of: {', '.join(sorted(DISPATCH_ROLES))}"
            ),
        )

    # Construct dispatch intent
    event = _construct_dispatch_event(
        role, request.issue_number, request.branch, request.actor
    )
    if event is None:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to construct dispatch event for role {role}",
        )

    # Import publish function
    from vibe3.models import publish

    # Publish the dispatch intent
    try:
        publish(event)
        logger.bind(domain="control-plane").info(
            f"Published dispatch intent for role {role} via control-plane API",
            extra={
                "role": role,
                "issue_number": request.issue_number,
                "branch": request.branch,
                "actor": request.actor,
                "source": request.source,
            },
        )
    except Exception as exc:
        logger.exception(f"Failed to publish dispatch intent: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish dispatch intent: {exc}",
        )

    # Publish audit event
    from vibe3.models import ControlPlaneEventPublished

    audit_event = ControlPlaneEventPublished(
        event_type=type(event).__name__,
        issue_number=request.issue_number,
        actor=request.actor,
        source=request.source,
        idempotency_key=request.idempotency_key,
        detail=f"Dispatch intent for {role} published via control-plane API",
    )

    try:
        publish(audit_event)
    except Exception as exc:
        # CRITICAL: Audit event publish failure means loss of accountability record.
        # Log with high priority but don't fail the request (per acceptance criteria).
        # TODO: Add monitoring/alerting for audit failures in production.
        logger.bind(domain="control-plane").error(
            f"CRITICAL: Failed to publish audit event for dispatch/{role} "
            f"(actor={request.actor}, issue={request.issue_number}, "
            f"key={request.idempotency_key[:16]}...). "
            f"Audit trail entry LOST. Error: {exc}"
        )

    return ApiResponse(
        status="ok",
        detail=f"Dispatch intent for {role} published",
        idempotency_key=request.idempotency_key,
    )


@router.get("/events", response_model=EventsResponse)
async def list_events(
    limit: int = Query(default=50, le=200),
    event_type: str | None = Query(default=None),
    _: str = Depends(verify_control_plane_token),
) -> EventsResponse:
    """List recent events.

    Args:
        limit: Maximum number of events to return
        event_type: Filter by event type (optional)
        _: Auth dependency (unused return value)

    Returns:
        EventsResponse with list of events
    """
    from vibe3.clients import SQLiteClient

    store = SQLiteClient()

    # Query events
    events_data = store.get_events(limit=limit, branch=None, event_type=event_type)

    # Convert to EventEntry models
    events = [
        EventEntry(
            id=e.get("id", 0),
            branch=e.get("branch", ""),
            event_type=e.get("event_type", ""),
            actor=e.get("actor", ""),
            detail=e.get("detail"),
            refs=e.get("refs"),
            created_at=e.get("created_at", ""),
        )
        for e in events_data
    ]

    return EventsResponse(events=events, count=len(events))


@router.get("/jobs", response_model=JobsResponse)
async def list_jobs(
    _: str = Depends(verify_control_plane_token),
) -> JobsResponse:
    """List active and recent jobs.

    Args:
        _: Auth dependency (unused return value)

    Returns:
        JobsResponse with active jobs, recent jobs, and summary
    """
    from vibe3.execution import JobMonitorService, get_actor_registry

    job_svc = JobMonitorService()
    registry = get_actor_registry()

    # Get job snapshots
    snapshot = job_svc.snapshot()

    # Convert active jobs
    active = [
        JobEntry(
            actor_id=job.actor_id,
            job_type=job.job_type,
            status=job.status.value if hasattr(job.status, "value") else job.status,
            issue_number=job.issue_number,
            branch=job.branch,
            started_at=job.started_at,
            completed_at=job.completed_at,
            pid=job.pid,
        )
        for job in snapshot.active_jobs
    ]

    # Convert recent jobs
    recent = [
        JobEntry(
            actor_id=job.actor_id,
            job_type=job.job_type,
            status=job.status.value if hasattr(job.status, "value") else job.status,
            issue_number=job.issue_number,
            branch=job.branch,
            started_at=job.started_at,
            completed_at=job.completed_at,
            pid=job.pid,
        )
        for job in snapshot.recent_jobs
    ]

    # Build summary
    summary = {
        "active_count": len(active),
        "recent_count": len(recent),
        "running_count": snapshot.running_count,
        "completed_count": snapshot.completed_count,
        "failed_count": snapshot.failed_count,
        "registry_size": registry.size() if hasattr(registry, "size") else 0,
    }

    return JobsResponse(active=active, recent=recent, summary=summary)
