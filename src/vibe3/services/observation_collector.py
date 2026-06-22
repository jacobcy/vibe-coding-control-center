"""Observation collector service for audit trail.

Provides structured observation collection with watermark-based deduplication.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from vibe3.models.audit_observation import (
    AuditObservation,
    ObservationLayer,
    ObservationSourceWindow,
)
from vibe3.models.flow import FlowState


class ObservationCollector:
    """Collects and persists audit observations with deduplication.

    Responsibilities:
    - Select candidate flows for observation
    - Check/record watermarks to avoid duplicate observations
    - Create structured observation records
    - Persist observations to shared directory

    Boundary:
    - Does NOT create suggestions, decisions, or prompt/material modifications
    - Does NOT directly write to GitHub issues/PRs
    - Does NOT write to SQLite database
    - Limits sampling to max 3 flows per collection
    """

    def __init__(self, shared_dir: Path | None = None):
        """Initialize collector with shared directory.

        Args:
            shared_dir: Path to .git/shared directory (defaults to git common dir)
        """
        if shared_dir is None:
            # Try to get git common dir
            import subprocess

            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--git-common-dir"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                git_dir = Path(result.stdout.strip())
                self.shared_dir = git_dir / "shared" / "observations"
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fallback to current worktree .git
                self.shared_dir = Path(".git") / "shared" / "observations"
        else:
            self.shared_dir = shared_dir / "observations"

        # Ensure directory exists
        self.shared_dir.mkdir(parents=True, exist_ok=True)

        self.watermarks_file = self.shared_dir / "watermarks.json"
        self._watermarks_cache: dict[str, str] | None = None

    def select_candidates(
        self, flows: list[FlowState], limit: int = 3
    ) -> list[FlowState]:
        """Select candidate flows for observation.

        Priority order:
        1. Recently blocked/aborted flows still affecting execution queue
        2. Flows with evidence across multiple sources (issue, PR, handoff, commit)
        3. Flows showing clear agent contract failures or scope mismatches
        4. Flows with recurring symptoms

        Args:
            flows: List of all flows
            limit: Maximum number of candidates to select (default 3)

        Returns:
            List of candidate flows to observe
        """
        candidates = []

        # Priority 1: blocked and aborted flows
        blocked = [f for f in flows if f.flow_status in ("blocked", "aborted")]
        candidates.extend(blocked)

        # Priority 2: active flows with blocked_reason (semantic blocked state)
        active_blocked = [
            f for f in flows if f.flow_status == "active" and f.blocked_reason
        ]
        candidates.extend(active_blocked)

        # Priority 3: stale flows that might have failed silently
        stale = [f for f in flows if f.flow_status == "stale"]
        candidates.extend(stale)

        # Priority 4: crashed executions
        crashed = [
            f
            for f in flows
            if f.executor_status == "crashed" or f.planner_status == "crashed"
        ]
        candidates.extend(crashed)

        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for f in candidates:
            if f.branch not in seen:
                seen.add(f.branch)
                unique_candidates.append(f)

        # Sort by updated_at (most recent first)
        unique_candidates.sort(key=lambda f: f.updated_at, reverse=True)

        # Limit to specified count
        return unique_candidates[:limit]

    def check_watermark(self, branch: str, current_watermark: str) -> bool:
        """Check if flow has already been observed with this watermark.

        Args:
            branch: Flow branch name
            current_watermark: Current watermark for the flow

        Returns:
            True if flow has been observed with this watermark (should skip)
        """
        watermarks = self._load_watermarks()
        previous_watermark = watermarks.get(branch)

        return previous_watermark == current_watermark

    def compute_watermark(
        self,
        flow: FlowState,
        prompt_hash: str | None = None,
    ) -> str:
        """Compute watermark for flow deduplication.

        Watermark is based on:
        - branch name
        - last updated timestamp
        - PR number (if any)
        - prompt hash (if provided)

        Args:
            flow: Flow to compute watermark for
            prompt_hash: Optional prompt hash for this flow

        Returns:
            16-character watermark hash
        """
        return AuditObservation.compute_watermark(
            branch=flow.branch,
            updated_at=flow.updated_at,
            pr_number=self._extract_pr_number(flow),
            prompt_hash=prompt_hash,
        )

    def _extract_pr_number(self, flow: FlowState) -> int | None:
        """Extract PR number from flow's pr_ref field.

        Args:
            flow: Flow to extract PR number from

        Returns:
            PR number if found, None otherwise
        """
        if not flow.pr_ref:
            return None

        # pr_ref is expected to be a PR URL like:
        # https://github.com/owner/repo/pull/123
        try:
            parts = flow.pr_ref.split("/")
            if "pull" in parts:
                idx = parts.index("pull")
                if idx + 1 < len(parts):
                    return int(parts[idx + 1])
        except (ValueError, IndexError):
            pass

        return None

    def collect(
        self,
        flows: list[FlowState],
        dry_run: bool = False,
        prompt_hashes: dict[str, str] | None = None,
    ) -> list[AuditObservation]:
        """Collect observations for candidate flows.

        Args:
            flows: List of flows to observe
            dry_run: If True, don't persist observations
            prompt_hashes: Optional dict mapping branch to prompt hash

        Returns:
            List of created observations
        """
        candidates = self.select_candidates(flows)
        observations = []

        prompt_hashes = prompt_hashes or {}

        for flow in candidates:
            # Compute watermark
            prompt_hash = prompt_hashes.get(flow.branch)
            watermark = self.compute_watermark(flow, prompt_hash)

            # Check if already observed with this watermark
            if self.check_watermark(flow.branch, watermark):
                continue

            # Create observation
            observation = self._create_observation(flow, watermark, prompt_hash)

            if observation:
                observations.append(observation)

                # Persist unless dry-run
                if not dry_run:
                    self._persist_observation(observation)
                    self._record_watermark(flow.branch, watermark)

        return observations

    def _create_observation(
        self,
        flow: FlowState,
        watermark: str,
        prompt_hash: str | None,
    ) -> AuditObservation | None:
        """Create observation from flow state.

        Args:
            flow: Flow to create observation for
            watermark: Computed watermark
            prompt_hash: Optional prompt hash

        Returns:
            Created observation or None if unable to create
        """
        # Determine observation type and symptom
        observation_type, symptom, failure_pattern = self._classify_flow(flow)

        # Determine affected layer
        affected_layer = self._infer_affected_layer(flow)

        # Build source window
        source_window = ObservationSourceWindow(
            issue_number=self._extract_issue_number(flow),
            branch=flow.branch,
            pr_number=self._extract_pr_number(flow),
            prompt_hash=prompt_hash,
        )

        # Build evidence summary
        evidence_summary = self._build_evidence_summary(flow)

        # Determine confidence
        confidence = self._determine_confidence(flow)

        # Build raw refs
        raw_refs = self._build_raw_refs(flow)

        # Build limitations
        limitations = self._build_limitations(flow)

        return AuditObservation.create(
            observation_type=observation_type,
            source_window=source_window,
            symptom=symptom,
            affected_layer=affected_layer,
            evidence_summary=evidence_summary,
            confidence=confidence,
            created_by="cli/audit-observe",
            failure_pattern=failure_pattern,
            raw_refs=raw_refs,
            limitations=limitations,
            updated_at=flow.updated_at,
            prompt_hash=prompt_hash,
        )

    def _classify_flow(self, flow: FlowState) -> tuple[str, str, str | None]:
        """Classify flow to determine observation type and symptom.

        Returns:
            Tuple of (observation_type, symptom, failure_pattern)
        """
        if flow.flow_status == "blocked":
            return (
                "flow_blocked",
                f"Flow blocked: {flow.blocked_reason or 'unknown reason'}",
                "dependency_blocked",
            )
        elif flow.flow_status == "aborted":
            return (
                "flow_aborted",
                "Flow was aborted",
                "manual_abort",
            )
        elif flow.executor_status == "crashed":
            return (
                "execution_crashed",
                "Executor crashed during run",
                "runtime_crash",
            )
        elif flow.planner_status == "crashed":
            return (
                "planning_crashed",
                "Planner crashed during plan generation",
                "runtime_crash",
            )
        elif flow.flow_status == "stale":
            return (
                "flow_stale",
                "Flow became stale (no recent updates)",
                "timeout",
            )
        elif flow.blocked_reason:
            return (
                "flow_semantically_blocked",
                f"Flow marked blocked: {flow.blocked_reason}",
                "dependency_blocked",
            )
        else:
            return (
                "flow_anomaly",
                f"Flow in unusual state: {flow.flow_status}",
                None,
            )

    def _infer_affected_layer(self, flow: FlowState) -> ObservationLayer:
        """Infer which layer is affected based on flow state.

        Returns:
            ObservationLayer enum value
        """
        if flow.executor_status == "crashed" or flow.planner_status == "crashed":
            return ObservationLayer.RUNTIME

        if flow.blocked_reason and "dependency" in flow.blocked_reason.lower():
            return ObservationLayer.GOVERNANCE_POLICY

        # Default to runtime for now
        return ObservationLayer.RUNTIME

    def _extract_issue_number(self, flow: FlowState) -> int | None:
        """Extract issue number from flow's spec_ref or branch.

        Args:
            flow: Flow to extract issue number from

        Returns:
            Issue number if found, None otherwise
        """
        # Try to extract from branch name (e.g., task/issue-123-feature)
        if "issue-" in flow.branch:
            try:
                parts = flow.branch.split("-")
                if len(parts) >= 2:
                    return int(parts[1])
            except (ValueError, IndexError):
                pass

        return None

    def _build_evidence_summary(self, flow: FlowState) -> str:
        """Build evidence summary from flow state.

        Args:
            flow: Flow to summarize

        Returns:
            Evidence summary string
        """
        parts = [f"Flow status: {flow.flow_status}"]

        if flow.executor_status:
            parts.append(f"Executor: {flow.executor_status}")
        if flow.planner_status:
            parts.append(f"Planner: {flow.planner_status}")
        if flow.blocked_reason:
            parts.append(f"Blocked: {flow.blocked_reason}")
        if flow.updated_at:
            parts.append(f"Last update: {flow.updated_at}")

        return "; ".join(parts)

    def _determine_confidence(
        self, flow: FlowState
    ) -> Literal["high", "medium", "low"]:
        """Determine confidence level based on available evidence.

        Args:
            flow: Flow to assess

        Returns:
            Confidence level: "high", "medium", or "low"
        """
        evidence_count = 0

        # Check for multiple evidence sources
        if flow.spec_ref:
            evidence_count += 1
        if flow.pr_ref:
            evidence_count += 1
        if flow.plan_ref or flow.report_ref or flow.audit_ref:
            evidence_count += 1
        if flow.blocked_reason:
            evidence_count += 1

        if evidence_count >= 2:
            return "high"
        elif evidence_count >= 1:
            return "medium"
        else:
            return "low"

    def _build_raw_refs(self, flow: FlowState) -> dict[str, Any]:
        """Build raw refs dict from flow state.

        Args:
            flow: Flow to extract refs from

        Returns:
            Dict of reference info
        """
        refs: dict[str, Any] = {"flow": flow.branch}

        if flow.spec_ref:
            refs["spec_ref"] = flow.spec_ref
        if flow.pr_ref:
            refs["pr"] = flow.pr_ref
        if flow.plan_ref:
            refs["plan_ref"] = flow.plan_ref
        if flow.report_ref:
            refs["report_ref"] = flow.report_ref
        if flow.audit_ref:
            refs["audit_ref"] = flow.audit_ref

        return refs

    def _build_limitations(self, flow: FlowState) -> list[str]:
        """Build limitations list based on missing data.

        Args:
            flow: Flow to assess

        Returns:
            List of limitation strings
        """
        limitations = []

        if not flow.spec_ref:
            limitations.append("No spec_ref available")
        if not flow.pr_ref and flow.flow_status in ("done", "active"):
            limitations.append("No PR reference for active/done flow")
        if not flow.updated_at:
            limitations.append("Missing updated_at timestamp")

        return limitations

    def _persist_observation(self, observation: AuditObservation) -> Path:
        """Persist observation to shared directory.

        Args:
            observation: Observation to persist

        Returns:
            Path to created file
        """
        # Create filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = f"audit-observation-{timestamp}.yaml"
        filepath = self.shared_dir / filename

        # Write YAML content
        yaml_content = self._format_as_yaml(observation)
        filepath.write_text(yaml_content)

        return filepath

    def _format_as_yaml(self, observation: AuditObservation) -> str:
        """Format observation as YAML string.

        Args:
            observation: Observation to format

        Returns:
            YAML string
        """
        lines = [
            "audit_observation:",
            "  schema_version: 1",
            f"  created_at: {observation.created_at}",
            f"  created_by: {observation.created_by}",
            "",
            "  subject:",
        ]

        if observation.source_window.issue_number:
            lines.append(f"    issue_number: {observation.source_window.issue_number}")
        if observation.source_window.branch:
            lines.append(f"    branch: {observation.source_window.branch}")
        if observation.source_window.pr_number:
            lines.append(f"    pr_number: {observation.source_window.pr_number}")

        lines.extend(
            [
                "",
                "  observation:",
                f"    title: {observation.observation_type}",
                f"    symptom: {observation.symptom}",
            ]
        )

        if observation.failure_pattern:
            lines.append(f"    failure_pattern: {observation.failure_pattern}")

        lines.extend(
            [
                f"    affected_layer: {observation.affected_layer.value}",
                f"    confidence: {observation.confidence}",
                "",
                "  evidence:",
                f"    summary: {observation.evidence_summary}",
                f"    sample_count: {observation.sample_count}",
                "",
                "  source_watermark: {}".format(observation.source_watermark),
                "",
                "  limitations:",
            ]
        )

        for limitation in observation.limitations:
            lines.append(f"    - {limitation}")

        return "\n".join(lines) + "\n"

    def _load_watermarks(self) -> dict[str, str]:
        """Load watermarks from file.

        Returns:
            Dict mapping branch to watermark
        """
        if self._watermarks_cache is not None:
            return self._watermarks_cache

        if not self.watermarks_file.exists():
            self._watermarks_cache = {}
            return self._watermarks_cache

        try:
            content = self.watermarks_file.read_text()
            self._watermarks_cache = json.loads(content)
            return self._watermarks_cache
        except (json.JSONDecodeError, IOError):
            self._watermarks_cache = {}
            return self._watermarks_cache

    def _record_watermark(self, branch: str, watermark: str) -> None:
        """Record watermark for a branch.

        Args:
            branch: Branch name
            watermark: Watermark to record
        """
        watermarks = self._load_watermarks()
        watermarks[branch] = watermark

        # Persist to file
        try:
            content = json.dumps(watermarks, indent=2, sort_keys=True)
            self.watermarks_file.write_text(content)
            self._watermarks_cache = watermarks
        except IOError as e:
            # Log but don't fail
            print(f"Warning: Failed to record watermark: {e}")
