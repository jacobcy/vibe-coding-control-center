"""Handoff service implementation."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients import SQLiteClient
from vibe3.clients.git_client import GitClient
from vibe3.exceptions import UserError
from vibe3.execution.actor_support import (
    extract_role_from_actor,
)
from vibe3.models.flow import FlowEvent
from vibe3.models.verdict import VerdictRecord
from vibe3.services.artifact_parser import ArtifactParser
from vibe3.services.handoff_storage import HandoffStorage
from vibe3.services.signature_service import SignatureService
from vibe3.utils.path_helpers import (
    _SHARED_HANDOFF_PREFIX,
    GitClientProtocol,
)


class HandoffService:
    """Service for managing handoff records."""

    _AUTHORITATIVE_REF_KINDS = {"plan", "report", "audit"}
    _HANDOFF_EVENT_TYPES = {
        "handoff_plan",
        "handoff_report",
        "handoff_run",  # backward-compat: legacy event type
        "handoff_audit",
        "handoff_indicate",
        "plan_recorded",
        "report_recorded",  # new canonical name
        "run_recorded",  # backward-compat: legacy event type
        "audit_recorded",
        "handoff_ci_status",
        "handoff_pr_comment",
    }
    _SUCCESS_HANDOFF_EVENT_TYPES = {
        "handoff_plan",
        "handoff_report",
        "handoff_run",  # backward-compat: legacy name for handoff_report
        "handoff_audit",
        "handoff_indicate",
        "handoff_verdict",
        "handoff_ci_status",
        "handoff_pr_comment",
    }

    def __init__(
        self,
        store: SQLiteClient | None = None,
        git_client: GitClientProtocol | None = None,
    ) -> None:
        self.store = store or SQLiteClient()
        self.git_client = git_client or GitClient()
        self.storage = HandoffStorage(self.git_client)

    def get_handoff_events(
        self,
        branch: str,
        event_type_prefix: str | None = None,
        limit: int | None = None,
    ) -> list[FlowEvent]:
        """Return handoff events for a branch from the authoritative store.

        Handoff views should only show explicit handoff artifacts / verdict events.
        Runtime lifecycle and flow state events belong to `flow show`, not
        `handoff status`.

        Note: Both active events (handoff_plan/run/audit) and passive events
        (*_recorded) are included. Passive events serve as fallback records when
        active writes fail, so they should not be filtered out.
        """
        events_data = self.store.get_events(branch, event_type_prefix=event_type_prefix)
        handoff_events = [
            FlowEvent(**event)
            for event in events_data
            if event["event_type"] in self._HANDOFF_EVENT_TYPES
        ]
        if limit is not None:
            handoff_events = handoff_events[:limit]
        return handoff_events

    def get_success_handoff_events(
        self,
        branch: str,
        limit: int | None = None,
    ) -> list[FlowEvent]:
        """Return only successful artifact handoff events (plan/report/audit).

        Includes active handoff events (handoff_plan/report/audit) plus
        handoff_indicate (manager) and handoff_verdict (review verdict).

        Args:
            branch: Branch name to query events for.
            limit: Optional limit on number of events to return.

        Returns:
            List of FlowEvent objects representing successful artifact handoffs.
        """
        events_data = self.store.get_events(branch)
        success_events = [
            FlowEvent(**event)
            for event in events_data
            if event["event_type"] in self._SUCCESS_HANDOFF_EVENT_TYPES
        ]
        if limit is not None:
            success_events = success_events[:limit]
        return success_events

    def append_current_handoff(
        self,
        message: str,
        actor: str | None,
        kind: str = "note",
    ) -> Path:
        """Append a lightweight update block to current.md."""
        branch = self.git_client.get_current_branch()
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )
        return self.storage.append_current_handoff(message, effective_actor, kind)

    def _resolve_branch_worktree_root(self, branch: str) -> Path:
        worktree_root = self.git_client.find_worktree_path_for_branch(branch)
        if worktree_root is not None:
            return worktree_root

        current_root = self.git_client.get_worktree_root()
        if current_root:
            return Path(current_root)

        raise UserError("Cannot validate handoff ref without a worktree root")

    @staticmethod
    def _is_log_like_path(path: Path) -> bool:
        lowered_parts = [part.lower() for part in path.parts]
        for idx in range(len(lowered_parts) - 1):
            if lowered_parts[idx] == "temp" and lowered_parts[idx + 1] == "logs":
                return True
        return path.name.endswith(".async.log")

    def _validate_authoritative_ref(
        self, ref_kind: str, ref_value: str, branch: str
    ) -> None:
        if ref_kind.lower() not in self._AUTHORITATIVE_REF_KINDS:
            return

        worktree_root = self._resolve_branch_worktree_root(branch).resolve()
        ref_path = Path(ref_value).expanduser()
        resolved = (
            ref_path.resolve(strict=False)
            if ref_path.is_absolute()
            else (worktree_root / ref_path).resolve(strict=False)
        )

        if self._is_log_like_path(resolved):
            raise UserError(
                f"{ref_kind}_ref cannot point to execution logs under temp/logs: "
                f"{ref_value}"
            )
        git_common = Path(self.git_client.get_git_common_dir()).resolve()
        if resolved.is_relative_to(git_common):
            raise UserError(
                f"{ref_kind}_ref must point to an agent worktree document, "
                f"not shared handoff store: {ref_value}"
            )
        if not resolved.is_relative_to(worktree_root):
            raise UserError(
                f"{ref_kind}_ref must stay inside the agent worktree: {ref_value}"
            )

    def _record_ref(
        self,
        ref_kind: str,
        ref_value: str,
        next_step: str | None,
        blocked_by: str | None,
        actor: str | None,
        verdict: str | None = None,
    ) -> Path:
        """Internal helper to record an active handoff reference.

        Note: For passive artifact recording, use record_passive_artifact() instead.
        This method only handles active handoff events (handoff_plan/report/audit).
        """
        branch = self.git_client.get_current_branch()
        self._validate_authoritative_ref(ref_kind, ref_value, branch)
        # Inlined _normalize_ref_value
        ref_value = self.storage.normalize_ref_value(ref_value, branch)
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            branch,
            explicit_actor=actor,
        )

        handoff_path = self.storage.ensure_current_handoff()

        ref_field = f"{ref_kind.lower()}_ref"

        # Build flow state updates
        flow_updates = {ref_field: ref_value}
        actor_field_by_kind = {
            "plan": "planner_actor",
            "report": "executor_actor",
            "audit": "reviewer_actor",
        }
        actor_field = actor_field_by_kind.get(ref_kind.lower())
        if actor_field:
            flow_updates[actor_field] = effective_actor
        if next_step:
            flow_updates["next_step"] = next_step
        if blocked_by:
            flow_updates["blocked_by"] = blocked_by

        if verdict:
            role = extract_role_from_actor(effective_actor)
            record = VerdictRecord(
                verdict=verdict,  # type: ignore
                actor=effective_actor,
                role=role,
                timestamp=datetime.now(UTC),
                reason=next_step or f"Recorded {ref_kind} reference",
                issues=blocked_by,
                flow_branch=branch,
            )
            flow_updates["latest_verdict"] = record.model_dump_json()

        message = f"Recorded {ref_kind} reference: {ref_value}"
        if verdict:
            message = f"verdict: {verdict}\n{message}"
        if next_step:
            message += f"\nNext Step: {next_step}"
        if blocked_by:
            message += f"\nBlocked By: {blocked_by}"

        self.store.update_flow_state(branch, **flow_updates)

        event_refs: dict[str, str] = {"ref": ref_value}
        if verdict:
            event_refs["verdict"] = verdict

        # Active handoff event type (passive recorded via record_passive_artifact)
        event_type = f"handoff_{ref_kind.lower()}"
        self.store.add_event(
            branch,
            event_type,
            effective_actor,
            detail=message,
            refs=event_refs,
        )

        try:
            self.append_current_handoff(
                message=message,
                actor=effective_actor,
                kind=ref_kind.lower(),
            )
        except (OSError, PermissionError) as exc:
            logger.bind(
                domain="handoff",
                action="append_current_handoff_best_effort",
                branch=branch,
                ref_kind=ref_kind.lower(),
                handoff_path=str(handoff_path),
            ).warning(f"Skipping non-authoritative handoff file append: {exc}")

        return handoff_path

    def record_plan(
        self,
        plan_ref: str,
        next_step: str | None = None,
        blocked_by: str | None = None,
        actor: str | None = None,
    ) -> Path:
        """Record plan handoff reference."""
        return self._record_ref("plan", plan_ref, next_step, blocked_by, actor)

    def record_report(
        self,
        report_ref: str,
        next_step: str | None = None,
        blocked_by: str | None = None,
        actor: str | None = None,
    ) -> Path:
        """Record report handoff reference."""
        return self._record_ref("report", report_ref, next_step, blocked_by, actor)

    def record_audit(
        self,
        audit_ref: str,
        next_step: str | None = None,
        blocked_by: str | None = None,
        actor: str | None = None,
        verdict: str | None = None,
        is_system_auto: bool = False,
    ) -> Path:
        """Record audit handoff reference.

        If is_system_auto=True, creates a passive artifact via record_passive_artifact.
        Otherwise, creates an active handoff event.
        """
        if is_system_auto:
            # Use passive artifact recording for system auto-generated audits
            result = self.record_passive_artifact(
                kind="audit",
                content=audit_ref,
                actor=actor,
                branch=None,
                verdict=verdict,
                next_step=next_step,
                blocked_by=blocked_by,
            )
            # record_passive_artifact returns Path or None, but this method
            # always returns Path
            # If None (empty content), still return the handoff path
            if result is None:
                # Fallback: return current handoff path
                return self.storage.ensure_current_handoff()
            return result
        else:
            # Active handoff recording
            return self._record_ref(
                "audit",
                audit_ref,
                next_step,
                blocked_by,
                actor,
                verdict=verdict,
            )

    def record_indicate(
        self,
        indicate_ref: str,
        next_step: str | None = None,
        blocked_by: str | None = None,
        actor: str | None = None,
    ) -> Path:
        """Record manager indicate handoff reference."""
        return self._record_ref("indicate", indicate_ref, next_step, blocked_by, actor)

    def record_passive_artifact(
        self,
        *,
        kind: str,
        content: str,
        actor: str | None = None,
        metadata: dict[str, str] | None = None,
        branch: str | None = None,
        # Audit-specific optional parameters
        verdict: str | None = None,
        next_step: str | None = None,
        blocked_by: str | None = None,
    ) -> Path | None:
        """Record a shared fallback artifact without upgrading authoritative refs.

        Supports all three artifact kinds: plan, report, audit.
        Audit can optionally include verdict, next_step, blocked_by.

        Args:
            kind: Artifact kind ("plan", "report", or "audit")
            content: Artifact content
            actor: Actor string (resolved from signature service if None)
            metadata: Optional metadata dict
            branch: Target branch (current if None)
            verdict: Optional verdict value (audit only)
            next_step: Optional next step (audit only)
            blocked_by: Optional blocked by description (audit only)

        Returns:
            Path to created artifact, or None if content is empty

        Raises:
            UserError: If kind is not supported
        """
        if kind not in {"plan", "report", "audit"}:
            raise UserError(f"Unsupported passive artifact kind: {kind}")

        target_branch = branch or self.git_client.get_current_branch()
        effective_actor = SignatureService.resolve_for_branch(
            self.store,
            target_branch,
            explicit_actor=actor,
        )
        sanitized_content = ArtifactParser.sanitize_handoff_content(content).strip()
        if not sanitized_content:
            return None

        created = self.storage.create_artifact(
            prefix=kind,
            content=sanitized_content + "\n",
            branch=target_branch,
        )
        if created is None:
            return None
        _, artifact_path = created

        detail, extra_refs = ArtifactParser.build_artifact_detail(
            kind,
            sanitized_content,
            artifact_path,
            metadata=metadata,
        )

        # Build event_type (use "report_recorded" instead of "run_recorded")
        event_type = "report_recorded" if kind == "report" else f"{kind}_recorded"

        git_common = Path(self.git_client.get_git_common_dir())
        relative_ref = (
            str(artifact_path.relative_to(git_common))
            if artifact_path.is_absolute()
            else str(artifact_path)
        )
        # Normalize to @ prefix format for shared handoff artifacts
        # vibe3/handoff/task-xxx/plan.md → @task-xxx/plan.md
        if relative_ref.startswith(_SHARED_HANDOFF_PREFIX):
            ref_value = "@" + relative_ref[len(_SHARED_HANDOFF_PREFIX) :]
        else:
            ref_value = relative_ref

        # Build refs including audit-specific fields
        refs: dict[str, str | list[str]] = {"ref": ref_value}
        refs.update(extra_refs)

        # Add audit-specific refs if provided
        if kind == "audit":
            if verdict:
                refs["verdict"] = verdict
            # Add verdict and other fields to detail for audit
            detail_parts = [detail]
            if verdict:
                detail_parts.insert(0, f"verdict: {verdict}")
            if next_step:
                detail_parts.append(f"Next Step: {next_step}")
            if blocked_by:
                detail_parts.append(f"Blocked By: {blocked_by}")
            detail = "\n".join(detail_parts)

        self.store.add_event(
            target_branch,
            event_type,
            effective_actor,
            detail=detail,
            refs=refs,
        )
        return artifact_path

    def record_ci_status(
        self,
        branch: str,
        pr_number: int,
        status: str,
        actor: str = "system/github",
    ) -> bool:
        """Record CI status as external event.

        Only records if status changed from last recorded status.

        Args:
            branch: Branch name
            pr_number: PR number
            status: CI status string (e.g., "SUCCESS", "FAILURE", "PENDING")
            actor: Actor string (defaults to "system/github")

        Returns:
            True if event was recorded, False if skipped (no change)
        """
        # Query last recorded CI status for this branch
        last_events = self.get_handoff_events(
            branch, event_type_prefix="handoff_ci_status", limit=1
        )

        # Check if status changed
        if last_events and last_events[0].refs:
            last_status = last_events[0].refs.get("status")
            if last_status == status:
                logger.bind(
                    domain="handoff",
                    action="record_ci_status",
                    branch=branch,
                    pr_number=pr_number,
                    status=status,
                ).debug("CI status unchanged, skipping recording")
                return False

        # Record new status
        detail = f"PR #{pr_number} CI status: {status}"
        refs = {
            "pr_number": str(pr_number),
            "status": status,
        }

        self.store.add_event(
            branch,
            "handoff_ci_status",
            actor,
            detail=detail,
            refs=refs,
        )

        logger.bind(
            domain="handoff",
            action="record_ci_status",
            branch=branch,
            pr_number=pr_number,
            status=status,
        ).info("Recorded CI status change")
        return True

    def record_pr_comments(
        self,
        branch: str,
        pr_number: int,
        comments: list[dict[str, Any]],
        review_comments: list[dict[str, Any]] | None = None,
        actor: str = "system/github",
    ) -> int:
        """Record PR comments as external events.

        Only records comments not already recorded (dedup by comment ID).

        Args:
            branch: Branch name
            pr_number: PR number
            comments: List of general comments (each has 'id' or 'number' field)
            review_comments: List of review comments (each has 'id' field)
            actor: Actor string (defaults to "system/github")

        Returns:
            Number of new comments recorded
        """
        if review_comments is None:
            review_comments = []

        # Query existing recorded comment IDs
        existing_events = self.get_handoff_events(
            branch, event_type_prefix="handoff_pr_comment"
        )
        recorded_ids = set()
        for event in existing_events:
            if event.refs:
                comment_id = event.refs.get("comment_id")
                if comment_id:
                    recorded_ids.add(str(comment_id))

        # Record new comments
        recorded_count = 0
        all_comments = []

        # Process general comments (use 'id' or 'number' field)
        for comment in comments:
            comment_id = str(comment.get("id") or comment.get("number"))
            if comment_id and comment_id not in recorded_ids:
                all_comments.append(("general", comment_id, comment))

        # Process review comments (use 'id' field)
        for comment in review_comments:
            comment_id = str(comment.get("id"))
            if comment_id and comment_id not in recorded_ids:
                all_comments.append(("review", comment_id, comment))

        # Record each new comment
        for comment_type, comment_id, comment_data in all_comments:
            author = comment_data.get("author", {})
            author_login = (
                author.get("login", "unknown")
                if isinstance(author, dict)
                else str(author)
            )
            body = comment_data.get("body", "")
            created_at = comment_data.get("createdAt") or comment_data.get(
                "created_at", ""
            )

            # Truncate body for event detail (max 200 chars)
            truncated_body = body[:200] if len(body) > 200 else body

            detail = (
                f"PR #{pr_number} {comment_type} comment by "
                f"{author_login}: {truncated_body}"
            )
            refs = {
                "pr_number": str(pr_number),
                "comment_id": comment_id,
                "comment_type": comment_type,
                "author": author_login,
                "created_at": created_at,
            }

            self.store.add_event(
                branch,
                "handoff_pr_comment",
                actor,
                detail=detail,
                refs=refs,
            )
            recorded_count += 1

        if recorded_count > 0:
            logger.bind(
                domain="handoff",
                action="record_pr_comments",
                branch=branch,
                pr_number=pr_number,
                count=recorded_count,
            ).info(f"Recorded {recorded_count} new PR comments")

        return recorded_count
