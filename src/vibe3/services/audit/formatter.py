"""Audit evidence bundle formatting utilities."""

from vibe3.models import EvidenceBundle


def format_bundle_json(bundle: EvidenceBundle) -> str:
    """Format bundle as JSON string.

    Args:
        bundle: Evidence bundle to format

    Returns:
        JSON string representation
    """
    return bundle.model_dump_json(indent=2)


def format_bundle_summary(bundle: EvidenceBundle) -> str:
    """Format bundle as human-readable summary.

    Args:
        bundle: Evidence bundle to format

    Returns:
        Human-readable text summary
    """
    lines = [
        f"Evidence Bundle: {bundle.id}",
        f"Schema Version: {bundle.schema_version}",
        f"Created: {bundle.created_at}",
        f"Mode: {bundle.collection_context.mode}",
        "",
        "Primary Subject:",
        f"  Issue: {bundle.primary_subject.issue_number or 'N/A'}",
        f"  Branch: {bundle.primary_subject.branch or 'N/A'}",
        f"  PR: {bundle.primary_subject.pr_number or 'N/A'}",
        "",
        "Source References:",
        f"  GitHub: {len(bundle.source_refs.github)}",
        f"  Flow: {len(bundle.source_refs.flow)}",
        f"  Handoff: {len(bundle.source_refs.handoff)}",
        f"  Git: {len(bundle.source_refs.git)}",
        "",
        "Summary:",
        f"  Symptom: {bundle.summary.symptom}",
        f"  Evidence: {bundle.summary.evidence_text}",
        "",
        "Trust:",
        f"  Class: {bundle.trust.source_class}",
        f"  Freshness: {bundle.trust.freshness}",
        f"  Confidence: {bundle.trust.confidence}",
    ]

    if bundle.trust.limitations:
        lines.append("  Limitations:")
        for limitation in bundle.trust.limitations:
            lines.append(f"    - {limitation}")

    return "\n".join(lines)
