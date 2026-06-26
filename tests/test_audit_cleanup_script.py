"""Tests for the audit cleanup helper script."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    script_path = Path("scripts/audit-cleanup.py")
    spec = importlib.util.spec_from_file_location("audit_cleanup_script", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cleanup_matches_only_explicit_source_report(tmp_path: Path) -> None:
    module = _load_module()

    shared_dir = tmp_path / "shared"
    observations_dir = shared_dir / "observations"
    suggestions_dir = shared_dir / "suggestions"
    reports_dir = shared_dir / "reports"
    observations_dir.mkdir(parents=True)
    suggestions_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)

    obs_file = observations_dir / "audit-observation-20260626T120000.yaml"
    obs_file.write_text(
        """
audit_observation:
  observation_id: "obs-20260626T120000-aaaaaaaa"
""",
        encoding="utf-8",
    )
    sug_file = suggestions_dir / "audit-suggestion-20260626T120000-cluster.yaml"
    sug_file.write_text(
        """
audit_suggestion:
  suggestion_id: "sug-20260626T120000-bbbbbbbb"
  linked_observation_ids:
    - "obs-20260626T120000-aaaaaaaa"
""",
        encoding="utf-8",
    )

    targeted_report = reports_dir / "audit-report-20260626T120000.md"
    targeted_report.write_text(
        """---
linked_observation_ids:
  - obs-20260626T120000-aaaaaaaa
linked_suggestion_ids:
  - sug-20260626T120000-bbbbbbbb
---

# Targeted report
""",
        encoding="utf-8",
    )
    overlapping_report = reports_dir / "audit-report-20260626T130000.md"
    overlapping_report.write_text(
        """---
linked_observation_ids:
  - obs-20260626T120000-aaaaaaaa
linked_suggestion_ids:
  - sug-20260626T120000-bbbbbbbb
---

# Different report that shares evidence
""",
        encoding="utf-8",
    )

    issue_body = """
## Evidence Chain
- obs-20260626T120000-aaaaaaaa: [linked observation]
- sug-20260626T120000-bbbbbbbb: [linked suggestion]

---
**Source report**: audit-report-20260626T120000.md
"""

    obs_ids, sug_ids = module.extract_ids_from_issue_body(issue_body)
    report_refs = module.extract_report_refs_from_issue_body(issue_body)
    matched = module.find_matching_files(
        shared_dir,
        obs_ids,
        sug_ids,
        report_refs=report_refs,
    )

    assert matched.observations == [obs_file]
    assert matched.suggestions == [sug_file]
    assert matched.reports == [targeted_report]
