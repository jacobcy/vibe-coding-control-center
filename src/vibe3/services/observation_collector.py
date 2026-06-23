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
        observation_type, symptom, observed_failure_mode = self._classify_flow(flow)

        # Build source window with commit SHAs
        source_window = ObservationSourceWindow(
            issue_number=self._extract_issue_number(flow),
            branch=flow.branch,
            pr_number=self._extract_pr_number(flow),
            commit_shas=self._extract_commit_shas(flow),
            prompt_hash=prompt_hash,
            skill_ids=self._extract_skill_ids(flow),
            memory_ids=self._extract_memory_ids(flow),
        )

        # Build facts list
        facts = self._build_facts(flow)

        # Build interpretation
        interpretation = self._build_interpretation(flow, observed_failure_mode)

        # Determine confidence
        confidence = self._determine_confidence(flow)

        # Build limitations
        limitations = self._build_limitations(flow)

        # Build next_stage_input
        next_stage_input = self._build_next_stage_input(flow)

        return AuditObservation.create(
            observation_type=observation_type,
            source_window=source_window,
            symptom=symptom,
            observed_failure_mode=observed_failure_mode,
            confidence=confidence,
            created_by="cli/audit-observe",
            flow_status=flow.flow_status,
            facts=facts,
            interpretation=interpretation,
            limitations=limitations,
            next_stage_input=next_stage_input,
            updated_at=flow.updated_at,
            prompt_hash=prompt_hash,
        )

    def _classify_flow(self, flow: FlowState) -> tuple[
        str,
        str,
        Literal[
            "scope_mismatch",
            "missing_output",
            "state_loop",
            "contract_missing",
            "ci_failure",
            "review_gap",
            "unknown",
        ],
    ]:
        """Classify flow to determine observation type and symptom.

        Returns:
            Tuple of (observation_type, symptom, observed_failure_mode)
        """
        if flow.flow_status == "blocked":
            return (
                "flow_blocked",
                f"Flow blocked: {flow.blocked_reason or 'unknown reason'}",
                "contract_missing",  # dependency issues -> contract
            )
        elif flow.flow_status == "aborted":
            return (
                "flow_aborted",
                "Flow was aborted",
                "unknown",  # human decision
            )
        elif flow.executor_status == "crashed":
            return (
                "execution_crashed",
                "Executor crashed during run",
                "unknown",  # runtime failure
            )
        elif flow.planner_status == "crashed":
            return (
                "planning_crashed",
                "Planner crashed during plan generation",
                "unknown",  # runtime failure
            )
        elif flow.flow_status == "stale":
            return (
                "flow_stale",
                "Flow became stale (no recent updates)",
                "unknown",  # timeout
            )
        elif flow.blocked_reason:
            return (
                "flow_semantically_blocked",
                f"Flow marked blocked: {flow.blocked_reason}",
                "contract_missing",  # dependency issues
            )
        else:
            return (
                "flow_anomaly",
                f"Flow in unusual state: {flow.flow_status}",
                "unknown",
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

    def _extract_commit_shas(self, flow: FlowState) -> list[str]:
        """Extract commit SHAs from flow branch.

        Args:
            flow: Flow to extract commits from

        Returns:
            List of commit SHAs (last 5 commits on branch)
        """
        import subprocess

        try:
            # Get last 5 commits on branch
            result = subprocess.run(
                ["git", "log", "--oneline", "-5", "--format=%H", flow.branch],
                capture_output=True,
                text=True,
                check=True,
                timeout=5,
            )
            shas = result.stdout.strip().split("\n")
            return [sha for sha in shas if sha]
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return []

    def _extract_skill_ids(self, flow: FlowState) -> list[str]:
        """Extract skill IDs from flow metadata.

        Args:
            flow: Flow to extract skill IDs from

        Returns:
            List of skill IDs (placeholder for future integration)
        """
        # TODO: Integrate with skill registry to extract skill IDs
        # For now, return empty list as skills are not tracked in flow state
        return []

    def _extract_memory_ids(self, flow: FlowState) -> list[str]:
        """Extract memory IDs from claude-mem integration.

        Args:
            flow: Flow to extract memory IDs from

        Returns:
            List of memory IDs (placeholder for future integration)
        """
        # TODO: Integrate with claude-mem to extract relevant memory IDs
        # For now, return empty list as claude-mem is not integrated
        return []

    def _build_facts(self, flow: FlowState) -> list[dict[str, str]]:
        """Build facts list from flow state.

        Args:
            flow: Flow to extract facts from

        Returns:
            List of fact dicts with kind, ref, summary
        """
        facts = []

        # Flow fact
        facts.append(
            {
                "kind": "flow",
                "ref": flow.branch,
                "summary": f"Flow status: {flow.flow_status}",
            }
        )

        # GitHub issue fact
        if flow.spec_ref:
            facts.append(
                {
                    "kind": "github_issue",
                    "ref": f"https://github.com/jacobcy/vibe-coding-control-center/issues/{self._extract_issue_number(flow)}",
                    "summary": f"Issue bound to flow: {flow.spec_ref}",
                }
            )

        # GitHub PR fact
        if flow.pr_ref:
            facts.append(
                {
                    "kind": "github_pr",
                    "ref": flow.pr_ref,
                    "summary": "PR created for flow",
                }
            )

        # Handoff facts
        if flow.plan_ref:
            facts.append(
                {
                    "kind": "handoff",
                    "ref": "@plan",
                    "summary": f"Plan: {flow.plan_ref}",
                }
            )
        if flow.report_ref:
            facts.append(
                {
                    "kind": "handoff",
                    "ref": "@report",
                    "summary": f"Report: {flow.report_ref}",
                }
            )
        if flow.audit_ref:
            facts.append(
                {
                    "kind": "handoff",
                    "ref": "@audit",
                    "summary": f"Audit: {flow.audit_ref}",
                }
            )

        # Git commit facts
        commit_shas = self._extract_commit_shas(flow)
        if commit_shas:
            facts.append(
                {
                    "kind": "git",
                    "ref": f"{flow.branch} ({len(commit_shas)} commits)",
                    "summary": f"Recent commits: {', '.join(commit_shas[:3])}",
                }
            )

        return facts

    def _build_interpretation(
        self, flow: FlowState, observed_failure_mode: str
    ) -> dict[str, Any]:
        """Build interpretation structure.

        Args:
            flow: Flow being observed
            observed_failure_mode: Classified failure mode

        Returns:
            Interpretation dict with reasoning, likely_agent_failure,
            affected_material_candidates
        """
        affected_layer = self._infer_affected_layer(flow)

        interpretation = {
            "reasoning": (
                f"Flow in {flow.flow_status} state with "
                f"{observed_failure_mode} failure mode"
            ),
            "likely_agent_failure": "",
            "affected_material_candidates": [],
            "affected_layer": affected_layer.value,
        }

        # Add reasoning based on flow state
        if flow.executor_status == "crashed":
            interpretation["likely_agent_failure"] = "Executor crashed during execution"
        elif flow.planner_status == "crashed":
            interpretation["likely_agent_failure"] = "Planner crashed during planning"
        elif flow.blocked_reason:
            current_reason = str(interpretation.get("reasoning", ""))
            interpretation["reasoning"] = f"{current_reason}: {flow.blocked_reason}"

        return interpretation

    def _build_next_stage_input(self, flow: FlowState) -> dict[str, Any]:
        """Build next stage input for clustering.

        Args:
            flow: Flow being observed

        Returns:
            Next stage input dict with clustering hints
        """
        return {
            "suitable_for_clustering": True,
            "suggested_cluster_key": f"{flow.flow_status}-{flow.branch}",
            "requires_human_review": flow.flow_status in ("blocked", "aborted"),
        }

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
        """Format observation as YAML string aligned with governance schema.

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
            f"  source_material: {observation.source_material}",
            "",
            "  subject:",
        ]

        # Subject section
        if observation.source_window.issue_number:
            lines.append(f"    issue_number: {observation.source_window.issue_number}")
        if observation.source_window.branch:
            lines.append(f"    branch: {observation.source_window.branch}")
        if observation.source_window.pr_number:
            lines.append(f"    pr_number: {observation.source_window.pr_number}")
        lines.append(f"    flow_status: {observation.flow_status}")

        # Observation section
        lines.extend(
            [
                "",
                "  observation:",
                f"    title: {observation.observation_type}",
                f"    symptom: {observation.symptom}",
                f"    observed_failure_mode: {observation.observed_failure_mode}",
                f"    confidence: {observation.confidence}",
            ]
        )

        # Facts section
        lines.extend(["", "  facts:"])
        for fact in observation.facts:
            lines.extend(
                [
                    "    - kind: {}".format(fact.get("kind", "unknown")),
                    "      ref: {}".format(fact.get("ref", "")),
                    "      summary: {}".format(fact.get("summary", "")),
                ]
            )

        # Interpretation section
        lines.extend(["", "  interpretation:"])
        interp = observation.interpretation
        lines.append(f"    reasoning: {interp.get('reasoning', '')}")
        lines.append(
            f"    likely_agent_failure: {interp.get('likely_agent_failure', '')}"
        )
        lines.append("    affected_material_candidates:")
        for candidate in interp.get("affected_material_candidates", []):
            lines.append(f"      - {candidate}")
        if "affected_layer" in interp:
            lines.append(f"    affected_layer: {interp['affected_layer']}")

        # Limitations section
        lines.extend(["", "  limitations:"])
        for limitation in observation.limitations:
            lines.append(f"    - {limitation}")

        # Next stage input section
        lines.extend(["", "  next_stage_input:"])
        next_input = observation.next_stage_input
        suitable = next_input.get("suitable_for_clustering", True)
        lines.append(f"    suitable_for_clustering: {suitable}")
        if "suggested_cluster_key" in next_input:
            lines.append(
                f"    suggested_cluster_key: {next_input['suggested_cluster_key']}"
            )
        requires_review = next_input.get("requires_human_review", True)
        lines.append(f"    requires_human_review: {requires_review}")

        # Source watermark (for internal deduplication)
        lines.extend(["", f"  source_watermark: {observation.source_watermark}"])

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
