"""Verdict service implementation.

This service provides tools for recording and querying verdicts.
It follows the principle of "tools, not decisions":
- The service only records and queries data
- Decision logic is in agent prompts, not in code
"""

import json
from datetime import UTC, datetime
from typing import Literal

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.execution.actor_support import extract_role_from_actor
from vibe3.models.verdict import VerdictRecord
from vibe3.services.flow_service import FlowService
from vibe3.services.handoff_storage import HandoffStorage
from vibe3.services.signature_service import SignatureService
from vibe3.utils.git_path_client import GitPathProtocol


class VerdictService:
    """Service for managing verdict records.

    This service only records and queries verdicts. It does NOT make
    any decisions based on verdict values.

    Responsibilities:
    - Write verdict to handoff chain (append-only log)
    - Update flow state's latest_verdict field (quick query)
    - Query latest verdict from flow state

    NOT responsible for:
    - Interpreting verdict values
    - Making decisions based on verdict
    - Enforcing verdict-based workflows
    """

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitPathProtocol | None = None,
        flow_service: FlowService | None = None,
        handoff_storage: HandoffStorage | None = None,
    ) -> None:
        """Initialize verdict service.

        Args:
            store: SQLiteClient instance for persistence
            git_client: GitClient instance for git operations
            flow_service: FlowService instance
            handoff_storage: HandoffStorage instance
        """
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.flow_service = flow_service or FlowService(
            store=self.store, git_client=self.git_client
        )
        self.storage = handoff_storage or HandoffStorage(self.git_client)

    def write_verdict(
        self,
        verdict: Literal["PASS", "MAJOR", "BLOCK", "UNKNOWN"],
        reason: str | None = None,
        issues: str | None = None,
        branch: str | None = None,
    ) -> VerdictRecord:
        """Write verdict to handoff chain and flow state.

        This method:
        1. Resolves branch (current if not specified)
        2. Resolves actor (from signature service)
        3. Determines role (from context or default)
        4. Creates VerdictRecord
        5. Appends to handoff chain (authoritative log)
        6. Updates flow state's latest_verdict (quick query)

        Args:
            verdict: Verdict value (PASS, MAJOR, BLOCK, UNKNOWN)
            reason: Optional reason for the verdict
            issues: Optional issues description
            branch: Target branch (current if None)

        Returns:
            Created VerdictRecord

        Raises:
            UserError: If branch doesn't have an active flow
        """
        # 1. Resolve branch
        target_branch = branch or self.git_client.get_current_branch()

        logger.bind(
            domain="verdict",
            action="write",
            branch=target_branch,
            verdict=verdict,
        ).info("Writing verdict")

        # 2. Resolve actor
        actor = SignatureService.resolve_for_branch(
            self.store,
            target_branch,
            explicit_actor=None,
        )

        # 3. Determine role (from actor string or default to "agent")
        # Actor format: "role/backend" or "claude/claude-sonnet-4-6"
        role = extract_role_from_actor(actor)

        # 4. Create VerdictRecord
        record = VerdictRecord(
            verdict=verdict,
            actor=actor,
            role=role,
            timestamp=datetime.now(UTC),
            reason=reason,
            issues=issues,
            flow_branch=target_branch,
        )

        # 5. Append to handoff chain (authoritative)
        self.storage.append_current_handoff(
            message=record.to_handoff_markdown(),
            actor=actor,
            kind="verdict",
        )

        # 6. Update flow state (quick query)
        # Use Pydantic's JSON serialization to handle datetime
        self.store.update_flow_state(
            target_branch, latest_verdict=record.model_dump_json()
        )

        # 7. Persist event to event log
        # Only store verdict in refs, not in detail to avoid duplicate rendering
        self.store.add_event(
            target_branch,
            "handoff_verdict",
            actor,
            detail="",  # Empty detail, verdict value in refs only
            refs={"verdict": verdict, "reason": reason or ""},
        )

        logger.bind(
            domain="verdict",
            action="write",
            branch=target_branch,
            verdict=verdict,
            actor=actor,
        ).success("Verdict written successfully")

        return record

    def get_latest_verdict(self, branch: str) -> VerdictRecord | None:
        """Get latest verdict from flow state.

        Args:
            branch: Target branch

        Returns:
            Latest VerdictRecord or None
        """
        state = self.store.get_flow_state(branch)
        if not state:
            return None

        verdict_json = state.get("latest_verdict")
        if not verdict_json:
            return None

        try:
            data = json.loads(verdict_json)
            return VerdictRecord(**data)
        except Exception as e:
            logger.bind(
                domain="verdict",
                action="get_latest",
                branch=branch,
            ).warning(f"Failed to parse verdict data: {e}")
            return None
