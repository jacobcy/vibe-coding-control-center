#!/usr/bin/env python3
"""Summarize audit observation/suggestion YAML ledgers.

This helper intentionally stays outside the Vibe3 CLI/API surface. It provides
bounded, deterministic input summaries for governance materials; it does not
infer root causes, create decisions, or read the feedback database.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml


def _git_common_dir() -> Path:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            check=True,
            text=True,
            capture_output=True,
        )
        return Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path(".git")


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _load_yaml(path: Path, root_key: str) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get(root_key), dict):
        raise ValueError(f"missing {root_key} root")
    root = data[root_key]
    assert isinstance(root, dict)
    return root


def _observation_summary(path: Path) -> dict[str, Any]:
    data = _load_yaml(path, "audit_observation")
    observation = _dict(data.get("observation"))
    subject = _dict(data.get("subject"))
    next_stage = _dict(data.get("next_stage_input"))
    failure_mode = str(observation.get("observed_failure_mode") or "unknown")
    return {
        "file": path.name,
        "observation_id": str(data.get("observation_id") or path.stem),
        "created_at": str(data.get("created_at") or ""),
        "cluster_key": str(next_stage.get("suggested_cluster_key") or failure_mode),
        "failure_mode": failure_mode,
        "confidence": str(observation.get("confidence") or "low"),
        "issue_number": subject.get("issue_number"),
        "flow_status": str(subject.get("flow_status") or "unknown"),
    }


def _suggestion_summary(path: Path) -> dict[str, Any]:
    data = _load_yaml(path, "audit_suggestion")
    return {
        "suggestion_id": str(data.get("suggestion_id") or path.stem),
        "linked_observation_ids": [
            str(item) for item in _list(data.get("linked_observation_ids"))
        ],
        "recommended_action": str(data.get("recommended_action") or "evaluate_more"),
        "target_refs": [str(item) for item in _list(data.get("target_refs"))],
    }


def _read_observations(
    directory: Path, limit: int
) -> tuple[list[dict[str, Any]], list[str]]:
    if not directory.exists():
        return [], [f"Observation directory not found: {directory}"]
    observations: list[dict[str, Any]] = []
    limitations: list[str] = []
    for path in sorted(directory.glob("audit-observation-*.y*ml"))[:limit]:
        try:
            observations.append(_observation_summary(path))
        except Exception as exc:
            limitations.append(f"Skipped {path.name}: {exc}")
    return observations, limitations


def _read_suggestions(
    directory: Path, limit: int
) -> tuple[list[dict[str, Any]], list[str]]:
    if not directory.exists():
        return [], [f"Suggestion directory not found: {directory}"]
    suggestions: list[dict[str, Any]] = []
    limitations: list[str] = []
    for path in sorted(directory.glob("audit-suggestion-*.y*ml"))[:limit]:
        try:
            suggestions.append(_suggestion_summary(path))
        except Exception as exc:
            limitations.append(f"Skipped {path.name}: {exc}")
    return suggestions, limitations


def _clusters(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for observation in observations:
        grouped.setdefault(str(observation["cluster_key"]), []).append(observation)

    result: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        result.append(
            {
                "cluster_key": key,
                "observation_count": len(items),
                "observation_ids": [str(item["observation_id"]) for item in items],
                "failure_modes": sorted({str(item["failure_mode"]) for item in items}),
                "confidences": sorted(
                    {str(item["confidence"]) for item in items},
                    key=("high", "medium", "low").index,
                ),
                "issue_numbers": [
                    item["issue_number"]
                    for item in items
                    if item.get("issue_number") is not None
                ],
            }
        )
    return result


def main() -> None:
    git_common = _git_common_dir()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--observations-dir",
        type=Path,
        default=git_common / "shared" / "observations",
    )
    parser.add_argument(
        "--suggestions-dir",
        type=Path,
        default=git_common / "shared" / "suggestions",
    )
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    observations, observation_limits = _read_observations(
        args.observations_dir, args.limit
    )
    suggestions, suggestion_limits = _read_suggestions(args.suggestions_dir, args.limit)

    print(
        json.dumps(
            {
                "source": "yaml-ledger",
                "observations_dir": str(args.observations_dir),
                "suggestions_dir": str(args.suggestions_dir),
                "observation_count": len(observations),
                "suggestion_count": len(suggestions),
                "clusters": _clusters(observations),
                "suggestions": suggestions,
                "limitations": observation_limits + suggestion_limits,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
