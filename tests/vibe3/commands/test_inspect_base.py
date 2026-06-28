"""CLI contract tests for evidence-only inspect base."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import yaml
from typer.testing import CliRunner

from vibe3.commands.inspect import app
from vibe3.models.inspect_evidence import (
    ChangedFileFact,
    ChangeObservation,
    ChangePartitionSummary,
    ChangeSummary,
    ComparisonObservation,
    KernelHit,
    KernelImpact,
    KernelObservation,
    ReviewDepth,
    ReviewObservation,
    ReviewPolicy,
)

runner = CliRunner()


def _observation(*, status: str = "ready") -> ReviewObservation:
    if status == "error":
        return ReviewObservation(status="error")
    fact = ChangedFileFact(
        path="src/vibe3/runtime/heartbeat.py",
        status="M",
        additions=3,
        deletions=1,
    )
    hit = KernelHit(
        path=fact.path,
        responsibilities=["heartbeat_timer"],
        reason="Drives reconciliation timing",
        review_floor=ReviewDepth.REPEATED,
        sources=["committed"],
    )
    return ReviewObservation(
        status="ready",
        comparison=ComparisonObservation(
            current_branch="feature/test",
            head_sha="a" * 40,
            requested_base=None,
            resolved_base="feature/root",
            merge_base_sha="b" * 40,
        ),
        changes=ChangeObservation(
            committed=[fact],
            summary=ChangeSummary(
                committed=ChangePartitionSummary(files=1, additions=3, deletions=1),
                unique_paths=1,
            ),
        ),
        kernel=KernelObservation(
            status="ready",
            impact=KernelImpact.LARGE,
            architecture_hits=[hit],
        ),
        review=ReviewPolicy(
            minimum_depth=ReviewDepth.REPEATED,
            reasons=[hit.reason],
        ),
    )


def _invoke_with_observation(
    args: list[str], observation: ReviewObservation
) -> tuple[object, MagicMock]:
    flow_state = MagicMock(creation_source=None)
    resolved = MagicMock(base_branch="feature/root")
    with (
        patch("vibe3.utils.get_current_branch", return_value="feature/test"),
        patch(
            "vibe3.services.flow.FlowService.get_flow_status",
            return_value=flow_state,
        ),
        patch(
            "vibe3.commands.pr_helpers.BaseResolutionUsecase.resolve_inspect_base",
            return_value=resolved,
        ) as resolve,
        patch(
            "vibe3.commands.inspect_base.build_review_observation",
            return_value=observation,
        ),
    ):
        return runner.invoke(app, args), resolve


def test_inspect_base_json_emits_versioned_evidence_contract() -> None:
    result, _ = _invoke_with_observation(["base", "--json"], _observation())

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == 1
    assert payload["comparison"]["merge_base_sha"] == "b" * 40
    assert payload["kernel"]["impact"] == "large"
    assert payload["review"]["minimum_depth"] == "repeated"
    assert payload["impact_analysis"] == {
        "status": "disabled",
        "reason": "benchmark_gate_failed",
    }
    assert "score" not in payload
    assert "impacted_modules" not in payload


def test_inspect_base_yaml_emits_versioned_evidence_contract() -> None:
    result, _ = _invoke_with_observation(["base", "--yaml"], _observation())

    assert result.exit_code == 0
    payload = yaml.safe_load(result.output)
    assert payload["schema_version"] == 1
    assert payload["comparison"]["merge_base_sha"] == "b" * 40
    assert payload["kernel"]["impact"] == "large"


def test_inspect_base_human_output_explains_kernel_evidence() -> None:
    result, _ = _invoke_with_observation(["base"], _observation())

    assert result.exit_code == 0
    assert "feature/test vs feature/root" in result.output
    assert "Kernel impact: large" in result.output
    assert "Minimum review depth: repeated" in result.output
    assert "src/vibe3/runtime/heartbeat.py" in result.output
    assert "Impact analysis: disabled (benchmark_gate_failed)" in result.output


def test_inspect_base_uses_shared_base_resolver() -> None:
    result, resolve = _invoke_with_observation(["base", "--json"], _observation())

    assert result.exit_code == 0
    resolve.assert_called_once_with(
        None,
        current_branch="feature/test",
        creation_source=None,
    )


def test_inspect_base_json_error_contract_returns_nonzero() -> None:
    result, _ = _invoke_with_observation(
        ["base", "missing", "--json"], _observation(status="error")
    )

    assert result.exit_code == 1
    assert json.loads(result.output)["status"] == "error"


def test_inspect_base_help_describes_evidence_not_impact_prediction() -> None:
    result = runner.invoke(app, ["base", "--help"])

    assert result.exit_code == 0
    assert "Git" in result.output
    assert "Kernel" in result.output
