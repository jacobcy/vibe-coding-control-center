"""Tests for the audit ledger summary helper script."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_audit_ledger_summary_lists_yaml_clusters(tmp_path: Path) -> None:
    observations = tmp_path / "observations"
    suggestions = tmp_path / "suggestions"
    observations.mkdir()
    suggestions.mkdir()
    (observations / "audit-observation-a.yaml").write_text(
        """
audit_observation:
  observation_id: "obs-a"
  created_at: "2026-06-23T10:00:00Z"
  subject:
    issue_number: 101
    flow_status: "blocked"
  observation:
    observed_failure_mode: "missing_output"
    confidence: "high"
  next_stage_input:
    suggested_cluster_key: "missing-report-ref"
""",
        encoding="utf-8",
    )
    (observations / "audit-observation-b.yaml").write_text(
        """
audit_observation:
  observation_id: "obs-b"
  created_at: "2026-06-23T11:00:00Z"
  subject:
    issue_number: 102
    flow_status: "failed"
  observation:
    observed_failure_mode: "missing_output"
    confidence: "medium"
  next_stage_input:
    suggested_cluster_key: "missing-report-ref"
""",
        encoding="utf-8",
    )
    (suggestions / "audit-suggestion-a.yaml").write_text(
        """
audit_suggestion:
  suggestion_id: "sug-a"
  linked_observation_ids:
    - "obs-a"
    - "obs-b"
  recommended_action: "bounded_edit"
  target_refs:
    - "supervisor/policies/run.md"
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/audit-ledger-summary.py",
            "--observations-dir",
            str(observations),
            "--suggestions-dir",
            str(suggestions),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    data = json.loads(result.stdout)
    assert data["source"] == "yaml-ledger"
    assert data["observation_count"] == 2
    assert data["suggestion_count"] == 1
    assert data["clusters"] == [
        {
            "cluster_key": "missing-report-ref",
            "observation_count": 2,
            "observation_ids": ["obs-a", "obs-b"],
            "failure_modes": ["missing_output"],
            "confidences": ["high", "medium"],
            "issue_numbers": [101, 102],
        }
    ]
    assert data["suggestions"] == [
        {
            "suggestion_id": "sug-a",
            "suggestion_source": "runtime_observation",
            "linked_observation_ids": ["obs-a", "obs-b"],
            "recommended_action": "bounded_edit",
            "target_refs": ["supervisor/policies/run.md"],
            "cluster_key": "unknown",
            "evidence_ref_count": 0,
        }
    ]
    assert data["suggestion_sources"] == {"runtime_observation": 1}
    assert data["limitations"] == []


def test_audit_ledger_summary_reports_bad_yaml_as_limitation(tmp_path: Path) -> None:
    observations = tmp_path / "observations"
    observations.mkdir()
    (observations / "audit-observation-bad.yaml").write_text(
        "audit_observation: [",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/audit-ledger-summary.py",
            "--observations-dir",
            str(observations),
            "--suggestions-dir",
            str(tmp_path / "missing"),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    data = json.loads(result.stdout)
    assert data["observation_count"] == 0
    assert "audit-observation-bad.yaml" in data["limitations"][0]
    assert "Suggestion directory not found" in data["limitations"][1]


def test_audit_ledger_summary_distinguishes_runtime_and_code_suggestions(
    tmp_path: Path,
) -> None:
    observations = tmp_path / "observations"
    suggestions = tmp_path / "suggestions"
    observations.mkdir()
    suggestions.mkdir()
    (observations / "audit-observation-a.yaml").write_text(
        """
audit_observation:
  observation_id: "obs-a"
  created_at: "2026-06-23T10:00:00Z"
  subject:
    issue_number: 101
    flow_status: "blocked"
  observation:
    observed_failure_mode: "state_loop"
    confidence: "high"
  next_stage_input:
    suggested_cluster_key: "state-loop"
""",
        encoding="utf-8",
    )
    (suggestions / "audit-suggestion-runtime.yaml").write_text(
        """
audit_suggestion:
  suggestion_id: "sug-runtime"
  suggestion_source: "runtime_observation"
  linked_observation_ids:
    - "obs-a"
  recommended_action: "bounded_edit"
  target_refs:
    - "supervisor/governance/run.md"
  evidence_refs:
    - "obs-a"
  evidence_summary:
    cluster_key: "state-loop"
""",
        encoding="utf-8",
    )
    (suggestions / "audit-suggestion-code.yaml").write_text(
        """
audit_suggestion:
  suggestion_id: "sug-code"
  suggestion_source: "code_auditor"
  linked_observation_ids: []
  recommended_action: "create_followup"
  target_refs:
    - "src/vibe3/services/flow_service.py"
  evidence_refs:
    - "src/vibe3/services/flow_service.py:42"
  evidence_summary:
    cluster_key: "roundabout_logic"
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/audit-ledger-summary.py",
            "--observations-dir",
            str(observations),
            "--suggestions-dir",
            str(suggestions),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    data = json.loads(result.stdout)

    assert data["suggestion_sources"] == {
        "code_auditor": 1,
        "runtime_observation": 1,
    }
    assert data["suggestions"] == [
        {
            "suggestion_id": "sug-code",
            "suggestion_source": "code_auditor",
            "linked_observation_ids": [],
            "recommended_action": "create_followup",
            "target_refs": ["src/vibe3/services/flow_service.py"],
            "cluster_key": "roundabout_logic",
            "evidence_ref_count": 1,
        },
        {
            "suggestion_id": "sug-runtime",
            "suggestion_source": "runtime_observation",
            "linked_observation_ids": ["obs-a"],
            "recommended_action": "bounded_edit",
            "target_refs": ["supervisor/governance/run.md"],
            "cluster_key": "state-loop",
            "evidence_ref_count": 1,
        },
    ]
