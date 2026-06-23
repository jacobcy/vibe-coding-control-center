"""Standalone SQLite client for feedback_observations CRUD operations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from loguru import logger

from vibe3.clients.sqlite_base import SQLiteClientBase
from vibe3.models.audit_observation import AuditObservation


class FeedbackStore(SQLiteClientBase):
    """Standalone SQLite client for feedback_observations table.

    Extends SQLiteClientBase for connection management.
    Not mixed into SQLiteClient facade - keeps feedback logic isolated.
    """

    def insert(self, observation: AuditObservation) -> str:
        """Insert observation, deduplicating by source_watermark.

        Args:
            observation: Validated AuditObservation to persist

        Returns:
            observation_id of inserted record

        Raises:
            sqlite3.IntegrityError: If observation_id already exists (rare)
        """
        row = self._model_to_row(observation)
        conn = self._get_connection()

        # Dedup check: skip if watermark already exists
        existing = conn.execute(
            "SELECT observation_id FROM feedback_observations "
            "WHERE source_watermark = ?",
            (row["source_watermark"],),
        ).fetchone()

        if existing:
            logger.bind(
                external="sqlite",
                operation="feedback_store",
            ).warning(
                f"Observation with watermark {row['source_watermark'][:8]}... "
                f"already exists as {existing[0]}, skipping insert"
            )
            return str(existing[0])

        conn.execute(
            """
            INSERT INTO feedback_observations (
                observation_id, observation_type, source_material,
                subject_issue_number, subject_branch, subject_pr_number,
                subject_commit_shas, subject_prompt_hash, subject_skill_ids,
                subject_memory_ids, flow_status, symptom, observed_failure_mode,
                confidence, facts, interpretation_reasoning,
                interpretation_likely_agent_failure,
                interpretation_affected_material_candidates, limitations,
                suitable_for_clustering, suggested_cluster_key,
                requires_human_review, created_by, created_at, source_watermark
            ) VALUES (
                :observation_id, :observation_type, :source_material,
                :subject_issue_number, :subject_branch, :subject_pr_number,
                :subject_commit_shas, :subject_prompt_hash, :subject_skill_ids,
                :subject_memory_ids, :flow_status, :symptom,
                :observed_failure_mode, :confidence, :facts,
                :interpretation_reasoning, :interpretation_likely_agent_failure,
                :interpretation_affected_material_candidates, :limitations,
                :suitable_for_clustering, :suggested_cluster_key,
                :requires_human_review, :created_by, :created_at, :source_watermark
            )
            """,
            row,
        )
        conn.commit()

        logger.bind(
            external="sqlite",
            operation="feedback_store",
        ).debug(f"Inserted observation {observation.observation_id}")

        return observation.observation_id

    def get_by_id(self, observation_id: str) -> dict[str, Any] | None:
        """Get observation by ID.

        Args:
            observation_id: Unique observation identifier

        Returns:
            Row dict with all fields, or None if not found
        """
        conn = self._get_connection()
        # Set row factory to get dict-like rows
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT * FROM feedback_observations WHERE observation_id = ?",
            (observation_id,),
        ).fetchone()

        if row is None:
            return None

        return dict(row)

    def list_observations(
        self,
        source: str | None = None,
        symptom: str | None = None,
        failure_mode: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List observations with optional filters.

        Args:
            source: Filter by source_material (exact match)
            symptom: Filter by symptom (substring match)
            failure_mode: Filter by observed_failure_mode (exact match)
            limit: Max results to return

        Returns:
            List of row dicts, newest first
        """
        conn = self._get_connection()
        query = "SELECT * FROM feedback_observations WHERE 1=1"
        params: list[Any] = []

        if source:
            query += " AND source_material = ?"
            params.append(source)

        if symptom:
            query += " AND symptom LIKE ?"
            params.append(f"%{symptom}%")

        if failure_mode:
            query += " AND observed_failure_mode = ?"
            params.append(failure_mode)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        # Set row factory to get dict-like rows
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_stats(self, group_by: str = "failure_mode") -> dict[str, int]:
        """Get aggregated statistics.

        Args:
            group_by: Field to group by ('failure_mode' or 'cluster_key')

        Returns:
            Dict mapping group value to count
        """
        conn = self._get_connection()

        if group_by == "failure_mode":
            field = "observed_failure_mode"
        elif group_by == "cluster_key":
            field = "suggested_cluster_key"
        else:
            raise ValueError(
                f"Invalid group_by: {group_by}. "
                f"Must be 'failure_mode' or 'cluster_key'"
            )

        rows = conn.execute(
            f"SELECT {field}, COUNT(*) as count "
            f"FROM feedback_observations "
            f"WHERE {field} IS NOT NULL "
            f"GROUP BY {field} "
            f"ORDER BY count DESC"
        ).fetchall()

        return {row[0]: row[1] for row in rows}

    def import_from_directory(self, dir_path: Path) -> tuple[int, int]:
        """Batch import YAML files from directory.

        Note: This is a helper for FeedbackImportService.
        Actual YAML parsing happens in the service layer.

        Args:
            dir_path: Directory containing .yaml/.yml files

        Returns:
            Tuple of (imported_count, skipped_count)

        Raises:
            FileNotFoundError: If directory doesn't exist
        """
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        # This method is a placeholder - actual YAML parsing
        # is delegated to FeedbackImportService which calls this store
        # for each parsed observation.
        return (0, 0)

    def _model_to_row(self, obs: AuditObservation) -> dict[str, Any]:
        """Convert AuditObservation to flat DB row dict.

        Handles the mapping from nested Pydantic model to denormalized DB columns.
        """
        return {
            "observation_id": obs.observation_id,
            "observation_type": obs.observation_type,
            "source_material": obs.source_material,
            # source_window denormalized
            "subject_issue_number": obs.source_window.issue_number,
            "subject_branch": obs.source_window.branch,
            "subject_pr_number": obs.source_window.pr_number,
            "subject_commit_shas": json.dumps(obs.source_window.commit_shas),
            "subject_prompt_hash": obs.source_window.prompt_hash,
            "subject_skill_ids": json.dumps(obs.source_window.skill_ids),
            "subject_memory_ids": json.dumps(obs.source_window.memory_ids),
            # core observation
            "flow_status": obs.flow_status,
            "symptom": obs.symptom,
            "observed_failure_mode": obs.observed_failure_mode,
            "confidence": obs.confidence,
            # structured evidence
            "facts": json.dumps(obs.facts),
            "interpretation_reasoning": obs.interpretation.get("reasoning"),
            "interpretation_likely_agent_failure": obs.interpretation.get(
                "likely_agent_failure"
            ),
            "interpretation_affected_material_candidates": json.dumps(
                obs.interpretation.get("affected_material_candidates", [])
            ),
            "limitations": json.dumps(obs.limitations),
            # next_stage_input
            "suitable_for_clustering": obs.next_stage_input.get(
                "suitable_for_clustering", True
            ),
            "suggested_cluster_key": obs.next_stage_input.get("suggested_cluster_key"),
            "requires_human_review": obs.next_stage_input.get(
                "requires_human_review", True
            ),
            # metadata
            "created_by": obs.created_by,
            "created_at": obs.created_at,
            "source_watermark": obs.source_watermark,
        }
