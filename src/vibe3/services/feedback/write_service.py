"""Feedback write service: YAML parsing, validation, and DB insertion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from vibe3.clients.feedback_store import FeedbackStore
from vibe3.models.audit_observation import (
    AuditObservation,
    ObservationSourceWindow,
)


class FeedbackWriteService:
    """Service for writing feedback observations from YAML sources."""

    def __init__(self, store: FeedbackStore | None = None) -> None:
        """Initialize with optional store dependency.

        Args:
            store: FeedbackStore instance. If None, creates a new one.
        """
        self.store = store or FeedbackStore()

    def write_from_file(self, path: Path) -> AuditObservation:
        """Read YAML file, validate, and insert observation.

        Args:
            path: Path to YAML file

        Returns:
            Validated AuditObservation that was inserted

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If YAML is invalid or validation fails
        """
        if not path.exists():
            raise FileNotFoundError(f"YAML file not found: {path}")

        content = path.read_text(encoding="utf-8")
        return self.write_from_stdin(content)

    def write_from_stdin(self, data: str) -> AuditObservation:
        """Parse YAML string, validate, and insert observation.

        Args:
            data: YAML content as string

        Returns:
            Validated AuditObservation that was inserted

        Raises:
            ValueError: If YAML is invalid or validation fails
        """
        parsed = self._parse_yaml(data)
        observation = self._yaml_to_model(parsed)
        self.store.insert(observation)

        logger.bind(
            external="feedback",
            operation="write",
        ).info(
            f"Wrote observation {observation.observation_id} "
            f"(failure_mode={observation.observed_failure_mode})"
        )

        return observation

    def validate_file(self, path: Path) -> tuple[bool, str | None]:
        """Validate YAML file against AuditObservation model.

        Args:
            path: Path to YAML file

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.
        """
        if not path.exists():
            return (False, f"File not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            parsed = self._parse_yaml(content)
            self._yaml_to_model(parsed)
            return (True, None)
        except ValueError as e:
            return (False, str(e))
        except Exception as e:
            return (False, f"Unexpected error: {e}")

    def _parse_yaml(self, content: str) -> dict[str, Any]:
        """Parse YAML and extract audit_observation key.

        Args:
            content: YAML content

        Returns:
            Parsed dict from audit_observation key

        Raises:
            ValueError: If YAML is invalid or missing audit_observation key
        """
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML: {e}") from e

        if not isinstance(data, dict):
            raise ValueError(f"YAML root must be a dict, got {type(data).__name__}")

        if "audit_observation" not in data:
            raise ValueError("YAML must have 'audit_observation' as root key")

        return dict(data["audit_observation"])

    def _yaml_to_model(self, data: dict[str, Any]) -> AuditObservation:
        """Convert nested YAML dict to flat AuditObservation model.

        The governance YAML uses nested structure:
        - subject: {issue_number, branch, pr_number, ...}
        - observation: {title, symptom, observed_failure_mode, ...}
        - interpretation: {reasoning, likely_agent_failure, ...}
        - facts: [...]
        - limitations: [...]
        - next_stage_input: {...}

        This method flattens it to match AuditObservation fields.

        Args:
            data: Parsed YAML dict under audit_observation key

        Returns:
            Validated AuditObservation

        Raises:
            ValueError: If validation fails
        """
        try:
            # Extract subject for source_window
            subject = data.get("subject", {})
            source_window = ObservationSourceWindow(
                issue_number=subject.get("issue_number"),
                branch=subject.get("branch"),
                pr_number=subject.get("pr_number"),
                commit_shas=subject.get("commit_shas", []),
                prompt_hash=subject.get("prompt_hash"),
                skill_ids=subject.get("skill_ids", []),
                memory_ids=subject.get("memory_ids", []),
            )

            # Extract observation fields
            observation = data.get("observation", {})

            # Map 'title' to 'observation_type' (field name differs)
            observation_type = observation.get(
                "title", observation.get("observation_type", "unknown")
            )

            # Extract interpretation
            interpretation = data.get("interpretation", {})

            # Build interpretation dict for model
            interpretation_dict: dict[str, Any] = {
                "reasoning": interpretation.get("reasoning"),
                "likely_agent_failure": interpretation.get("likely_agent_failure"),
                "affected_material_candidates": interpretation.get(
                    "affected_material_candidates", []
                ),
            }

            # Extract next_stage_input
            next_stage_input = data.get("next_stage_input", {})

            # Build observation
            obs = AuditObservation(
                observation_id=data.get("observation_id", ""),
                observation_type=observation_type,
                source_material=data.get(
                    "source_material",
                    "supervisor/governance/audit-observation.md",
                ),
                source_window=source_window,
                flow_status=data.get("flow_status", "unknown"),
                symptom=observation.get("symptom", ""),
                observed_failure_mode=observation.get(
                    "observed_failure_mode", "unknown"
                ),
                confidence=observation.get("confidence", "medium"),
                facts=data.get("facts", []),
                interpretation=interpretation_dict,
                limitations=data.get("limitations", []),
                next_stage_input=next_stage_input,
                created_by=data.get("created_by", "unknown"),
                created_at=data.get("created_at", ""),
                source_watermark=data.get("source_watermark", ""),
            )

            # Validate by accessing model fields (Pydantic will validate)
            # If no exception, model is valid
            return obs

        except Exception as e:
            raise ValueError(f"Failed to create AuditObservation: {e}") from e
