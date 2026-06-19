"""Provenance collection for dry-run prompt rendering."""

from __future__ import annotations

import hashlib

from vibe3.prompts import PromptManifest
from vibe3.prompts.models import (
    AnomalyFlags,
    PromptRenderProvenance,
    PromptVariableProvenance,
    SectionSourceProvenance,
)


def collect_dry_run_provenance(
    manifest: PromptManifest,
    recipe_key: str,
    variant_key: str,
    rendered_text: str,
    variable_provenance: tuple[PromptVariableProvenance, ...] = (),
    warnings: tuple[str, ...] = (),
) -> PromptRenderProvenance:
    """Build a PromptRenderProvenance record after rendering completes."""
    section_sources_list = manifest.get_section_sources(recipe_key, variant_key)
    section_sources = tuple(section_sources_list)

    rendered_hash = hashlib.sha256(rendered_text.encode("utf-8")).hexdigest()[:16]

    char_count = len(rendered_text)
    token_estimate_val = token_estimate(rendered_text)

    section_order = tuple(s.key for s in section_sources)
    anomalies = detect_anomalies(rendered_text, section_sources, section_order)

    return PromptRenderProvenance(
        recipe_key=recipe_key,
        variant_key=variant_key,
        section_order=section_order,
        section_sources=section_sources,
        variable_provenance=variable_provenance,
        rendered_hash=rendered_hash,
        char_count=char_count,
        token_estimate=token_estimate_val,
        warnings=warnings,
        anomalies=anomalies,
    )


def detect_anomalies(
    rendered_text: str,
    section_sources: tuple[SectionSourceProvenance, ...],
    section_order: tuple[str, ...],
) -> AnomalyFlags:
    """Detect audit anomalies from provenance data."""
    char_count = len(rendered_text)

    has_large_material = char_count > 200_000

    source_refs = [s.source_ref for s in section_sources if s.source_ref is not None]
    has_duplicate_material = len(source_refs) != len(set(source_refs))

    missing_output_contract = not any("output_format" in key for key in section_order)

    missing_verification_contract = not any(
        "exit_contract" in key for key in section_order
    )

    has_repo_profile = any(
        s.source_kind
        and s.source_ref
        and ("profile" in s.source_ref or "repo" in s.source_ref)
        for s in section_sources
    )

    has_project_policy_overlay = any(
        s.source_kind
        and s.source_ref
        and ("policy" in s.source_ref or "project" in s.source_ref)
        for s in section_sources
    )

    return AnomalyFlags(
        has_large_material=has_large_material,
        has_duplicate_material=has_duplicate_material,
        missing_output_contract=missing_output_contract,
        missing_verification_contract=missing_verification_contract,
        has_repo_profile=has_repo_profile,
        has_project_policy_overlay=has_project_policy_overlay,
    )


def token_estimate(text: str) -> int:
    """Rough token count: chars / 4."""
    return len(text) // 4
