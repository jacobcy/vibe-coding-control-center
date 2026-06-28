"""Renderers for the evidence-only inspect base result."""

from __future__ import annotations

from vibe3.models import ReviewObservation


def render_review_observation(observation: ReviewObservation) -> str:
    """Render human output from the same model used by JSON and YAML."""
    lines = [f"Observation status: {observation.status}"]
    comparison = observation.comparison
    if comparison is not None:
        lines.extend(
            [
                (
                    f"=== Branch Analysis: {comparison.current_branch} "
                    f"vs {comparison.resolved_base} ==="
                ),
                f"HEAD: {comparison.head_sha}",
                f"Merge base: {comparison.merge_base_sha}",
                "",
                "Changed files:",
                f"  Committed: {observation.changes.summary.committed.files}",
                f"  Staged: {observation.changes.summary.staged.files}",
                f"  Unstaged: {observation.changes.summary.unstaged.files}",
                f"  Untracked: {observation.changes.summary.untracked.files}",
                f"  Unique paths: {observation.changes.summary.unique_paths}",
            ]
        )

    if observation.kernel is not None:
        lines.extend(
            [
                "",
                f"Kernel status: {observation.kernel.status}",
                f"Kernel impact: {observation.kernel.impact}",
            ]
        )
        for hit in [
            *observation.kernel.architecture_hits,
            *observation.kernel.review_hits,
        ]:
            responsibilities = ", ".join(hit.responsibilities)
            sources = ", ".join(hit.sources)
            lines.append(f"  - {hit.path} [{responsibilities}; sources={sources}]")

    if observation.review is not None:
        lines.append(f"Minimum review depth: {observation.review.minimum_depth}")

    lines.extend(
        [
            "",
            (
                "Impact analysis: "
                f"{observation.impact_analysis.status} "
                f"({observation.impact_analysis.reason})"
            ),
        ]
    )
    diagnostics = [
        *observation.diagnostics,
        *(observation.kernel.diagnostics if observation.kernel else []),
    ]
    if diagnostics:
        lines.append("Diagnostics:")
        for diagnostic in diagnostics:
            path = f" [{diagnostic.path}]" if diagnostic.path else ""
            lines.append(f"  - {diagnostic.code}{path}: {diagnostic.message}")
    return "\n".join(lines)
