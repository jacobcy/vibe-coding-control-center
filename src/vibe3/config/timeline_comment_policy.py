"""Timeline event comment policy configuration."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from pydantic import BaseModel


class TimelineCommentPolicy(BaseModel):
    """Policy for whether timeline events should write GitHub comments.

    Events are categorized by purpose:
    - state_sync: Internal state synchronization (blocked, resumed, aborted)
    - runtime_error: Runtime failures (flow_failed)
    - artifact_ref: Artifact file references (plan/report/audit/indicate)
    - milestone: Important milestone events (verdict, pr_created, handoff_append)
    - human_readable: Human-visible state changes (state_transitioned)
    """

    # State sync events - NO COMMENTS (information in issue body or issue closed)
    state_sync_events: list[str] = [
        "flow_blocked",  # Blocked reason in issue body
        "resumed",  # Resume info in issue body
        "flow_aborted",  # Issue closed or PR closed, no need for comment
    ]

    # Runtime error events - NO COMMENTS (use vibe3 serve status)
    # These events intentionally omit issue_number to prevent comment writes
    runtime_error_events: list[str] = [
        "flow_failed",  # Runtime errors exposed via serve status
    ]

    # Artifact file references - NO COMMENTS (file paths in comments are useless)
    artifact_ref_events: list[str] = [
        "handoff_plan",  # plan_ref file path
        "handoff_report",  # report_ref file path
        "handoff_audit",  # audit_ref file path
        "handoff_indicate",  # indicate file path
        "plan_recorded",  # Legacy alias for handoff_plan
        "report_recorded",  # Legacy alias for handoff_report
    ]

    # Milestone events - WRITE COMMENTS (important progress markers)
    # NOTE: Must be routed through FlowTimelineService.record_timeline_event()
    # handoff_append is now routed through HandoffService.append_current_handoff()
    milestone_events: list[str] = [
        "handoff_append",  # Important milestone records (routed via HandoffService)
        "milestone_recorded",  # Example: Future milestone event (placeholder)
    ]

    # Human-readable events - WRITE COMMENTS (visible state changes)
    # NOTE: Must be routed through FlowTimelineService.record_timeline_event()
    # Future events will be added here when producers migrate to FlowTimelineService
    human_readable_events: list[str] = [
        "user_notification",  # Example: Future user-visible event (placeholder)
    ]

    # Events NOT routed through FlowTimelineService (for documentation)
    # These events are recorded directly with store.add_event() and bypass policy:
    # - pr_created: PRService creates PR (pr_service.py:310-315)
    # - handoff_verdict: VerdictService records verdict (verdict_service.py:140-146)
    # - state_transitioned: NoopGate state transition (noop_gate.py:406-424)
    #
    # handoff_append is NOW routed through FlowTimelineService via HandoffService
    # To enable policy filtering, route through FlowTimelineService first

    def should_write_comment(self, event_type: str) -> bool:
        """Check if event type should write GitHub comment.

        Args:
            event_type: Timeline event type

        Returns:
            True if should write comment, False otherwise
        """
        # State sync events - never write comments
        if event_type in self.state_sync_events:
            return False

        # Runtime error events - never write comments
        if event_type in self.runtime_error_events:
            return False

        # Artifact file references - never write comments
        if event_type in self.artifact_ref_events:
            return False

        # Milestone events - write comments
        if event_type in self.milestone_events:
            return True

        # Human-readable events - write comments
        if event_type in self.human_readable_events:
            return True

        # Unknown events - default to no comment (safe)
        return False

    @classmethod
    def from_yaml(cls, path: Path | None = None) -> TimelineCommentPolicy:
        """Load policy from YAML config file.

        Args:
            path: Path to YAML config file. If None, uses default path.

        Returns:
            TimelineCommentPolicy instance loaded from YAML or default instance.
        """
        from vibe3.config.loader import load_yaml_config

        yaml_path = path or Path("config/v3/timeline.yaml")
        data = load_yaml_config(yaml_path)

        if not data:
            return cls()  # 回退到硬编码默认值

        no_comment = data.get("no_comment", {})
        write_comment = data.get("write_comment", {})

        return cls(
            state_sync_events=no_comment.get(
                "state_sync", cls.model_fields["state_sync_events"].default
            ),
            runtime_error_events=no_comment.get(
                "runtime_error", cls.model_fields["runtime_error_events"].default
            ),
            artifact_ref_events=no_comment.get(
                "artifact_ref", cls.model_fields["artifact_ref_events"].default
            ),
            milestone_events=write_comment.get(
                "milestone", cls.model_fields["milestone_events"].default
            ),
            human_readable_events=write_comment.get(
                "human_readable", cls.model_fields["human_readable_events"].default
            ),
        )


def _load_default_policy() -> TimelineCommentPolicy:
    """Load default policy from YAML, fallback to hardcoded defaults.

    Returns:
        TimelineCommentPolicy instance from YAML or hardcoded defaults.
    """
    try:
        policy = TimelineCommentPolicy.from_yaml()
        if policy != TimelineCommentPolicy():
            logger.bind(domain="config", action="load").debug(
                "Timeline comment policy loaded from config/v3/timeline.yaml"
            )
        return policy
    except Exception:
        logger.bind(domain="config", action="load").warning(
            "Failed to load timeline.yaml, using hardcoded defaults"
        )
        return TimelineCommentPolicy()


# Default policy instance
DEFAULT_COMMENT_POLICY = _load_default_policy()
