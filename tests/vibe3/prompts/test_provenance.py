"""Tests for prompt provenance collection and anomaly detection."""

from __future__ import annotations

from pathlib import Path

from vibe3.prompts import PromptManifest
from vibe3.prompts.models import (
    PromptVariableProvenance,
    SectionSourceProvenance,
    VariableSourceKind,
)
from vibe3.prompts.provenance import (
    collect_dry_run_provenance,
    detect_anomalies,
    token_estimate,
)


def test_collect_dry_run_provenance_basic() -> None:
    """Verify provenance record has correct recipe_key, variant_key, section_order."""
    manifest = PromptManifest.load_default()
    provenance = collect_dry_run_provenance(
        manifest,
        recipe_key="plan.default",
        variant_key="first.bootstrap",
        rendered_text="test prompt",
    )

    assert provenance.recipe_key == "plan.default"
    assert provenance.variant_key == "first.bootstrap"
    assert isinstance(provenance.section_order, tuple)
    assert len(provenance.section_order) > 0


def test_collect_dry_run_provenance_hash() -> None:
    """Verify rendered_hash is consistent for same input."""
    manifest = PromptManifest.load_default()
    text = "test prompt content"

    provenance1 = collect_dry_run_provenance(
        manifest, "plan.default", "first.bootstrap", text
    )
    provenance2 = collect_dry_run_provenance(
        manifest, "plan.default", "first.bootstrap", text
    )

    assert provenance1.rendered_hash == provenance2.rendered_hash
    assert len(provenance1.rendered_hash) == 16  # First 16 chars of SHA-256


def test_collect_dry_run_provenance_size() -> None:
    """Verify char_count and token_estimate."""
    manifest = PromptManifest.load_default()
    text = "test prompt with more content"

    provenance = collect_dry_run_provenance(
        manifest, "plan.default", "first.bootstrap", text
    )

    assert provenance.char_count == len(text)
    assert provenance.token_estimate == len(text) // 4


def test_detect_anomalies_large_material() -> None:
    """Above threshold triggers flag."""
    # Create text larger than 200KB threshold
    large_text = "x" * 201_000
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(key="test"),
    )
    section_order: tuple[str, ...] = ("test",)

    anomalies = detect_anomalies(large_text, section_sources, section_order)

    assert anomalies.has_large_material is True


def test_detect_anomalies_no_large_material() -> None:
    """Below threshold does not trigger."""
    small_text = "small content"
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(key="test"),
    )
    section_order: tuple[str, ...] = ("test",)

    anomalies = detect_anomalies(small_text, section_sources, section_order)

    assert anomalies.has_large_material is False


def test_detect_anomalies_duplicate_material() -> None:
    """Same source_ref in two sections -> has_duplicate_material=True."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(key="s1", source_ref="file1.md"),
        SectionSourceProvenance(key="s2", source_ref="file1.md"),
    )
    section_order: tuple[str, ...] = ("s1", "s2")

    anomalies = detect_anomalies("text", section_sources, section_order)

    assert anomalies.has_duplicate_material is True


def test_detect_anomalies_no_duplicate() -> None:
    """Different source_refs -> has_duplicate_material=False."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(key="s1", source_ref="file1.md"),
        SectionSourceProvenance(key="s2", source_ref="file2.md"),
    )
    section_order: tuple[str, ...] = ("s1", "s2")

    anomalies = detect_anomalies("text", section_sources, section_order)

    assert anomalies.has_duplicate_material is False


def test_detect_anomalies_missing_output_contract() -> None:
    """No *.output_format section -> flag."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(key="header"),
    )
    section_order: tuple[str, ...] = ("header",)

    anomalies = detect_anomalies("text", section_sources, section_order)

    assert anomalies.missing_output_contract is True


def test_detect_anomalies_has_output_contract() -> None:
    """Has *.output_format -> no flag."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(key="header"),
        SectionSourceProvenance(key="planner.output_format"),
    )
    section_order: tuple[str, ...] = ("header", "planner.output_format")

    anomalies = detect_anomalies("text", section_sources, section_order)

    assert anomalies.missing_output_contract is False


def test_detect_anomalies_missing_verification_contract() -> None:
    """No *.exit_contract section -> flag."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(key="header"),
    )
    section_order: tuple[str, ...] = ("header",)

    anomalies = detect_anomalies("text", section_sources, section_order)

    assert anomalies.missing_verification_contract is True


def test_detect_anomalies_has_verification_contract() -> None:
    """Has *.exit_contract -> no flag."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(key="header"),
        SectionSourceProvenance(key="planner.exit_contract"),
    )
    section_order: tuple[str, ...] = ("header", "planner.exit_contract")

    anomalies = detect_anomalies("text", section_sources, section_order)

    assert anomalies.missing_verification_contract is False


def test_detect_anomalies_repo_profile() -> None:
    """Section with 'profile' path -> flag."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(
            key="repo",
            source_kind=VariableSourceKind.FILE,
            source_ref="config/profile/repo.md",
        ),
    )
    section_order: tuple[str, ...] = ("repo",)

    anomalies = detect_anomalies("text", section_sources, section_order)

    assert anomalies.has_repo_profile is True


def test_detect_anomalies_policy_overlay() -> None:
    """Section with 'policy' path -> flag."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(
            key="policy",
            source_kind=VariableSourceKind.FILE,
            source_ref="config/policy/project.md",
        ),
    )
    section_order: tuple[str, ...] = ("policy",)

    anomalies = detect_anomalies("text", section_sources, section_order)

    assert anomalies.has_project_policy_overlay is True


def test_get_section_sources_plan_default() -> None:
    """Verify metadata from plan.default recipe."""
    manifest = PromptManifest.load_default()
    section_sources = manifest.get_section_sources("plan.default", "first.bootstrap")

    assert len(section_sources) > 0
    assert isinstance(section_sources, list)
    assert all(isinstance(s, SectionSourceProvenance) for s in section_sources)


def test_get_section_sources_manager_with_source() -> None:
    """Verify file source is captured."""
    manifest = PromptManifest.load_default()
    # manager.default with first.bootstrap variant
    section_sources = manifest.get_section_sources("manager.default", "first.bootstrap")

    assert len(section_sources) > 0
    # Note: may be empty if all sections are provider-rendered, which is valid
    assert isinstance(section_sources[0].key, str)


def test_write_prompt_provenance_creates_file() -> None:
    """Verify JSON artifact is written."""
    # Import inside test to avoid circular dependency at module level
    from vibe3.observability.orchestra_log import write_prompt_provenance

    manifest = PromptManifest.load_default()
    provenance = collect_dry_run_provenance(
        manifest, "plan.default", "first.bootstrap", "test"
    )

    # Write with issue_number
    path = write_prompt_provenance(provenance, role="planner", issue_number=123)

    assert isinstance(path, Path)
    assert path.exists()
    assert path.suffix == ".json"
    assert "provenance_planner" in path.name

    # Cleanup
    path.unlink()


def test_write_prompt_provenance_valid_json() -> None:
    """Verify output is parseable JSON."""
    import json

    from vibe3.observability.orchestra_log import write_prompt_provenance

    manifest = PromptManifest.load_default()
    provenance = collect_dry_run_provenance(
        manifest, "plan.default", "first.bootstrap", "test"
    )

    path = write_prompt_provenance(provenance, role="planner", issue_number=456)

    # Read and parse JSON
    with open(path) as f:
        data = json.load(f)

    assert data["recipe_key"] == "plan.default"
    assert data["variant_key"] == "first.bootstrap"
    assert "section_order" in data
    assert "anomalies" in data

    # Cleanup
    path.unlink()


def test_get_section_sources_governance_scan_returns_material_catalog() -> None:
    """Template-based governance.scan should expose material_catalog
    as section sources."""
    manifest = PromptManifest.load_default()
    section_sources = manifest.get_section_sources("governance.scan", "")

    assert len(section_sources) > 0
    assert all(isinstance(s, SectionSourceProvenance) for s in section_sources)
    assert all(s.source_kind == VariableSourceKind.FILE for s in section_sources)
    assert all(s.source_ref is not None for s in section_sources)


def test_get_section_sources_run_plan_has_provider_sources() -> None:
    """run.plan sections should carry provider source attribution after YAML upgrade."""
    manifest = PromptManifest.load_default()
    section_sources = manifest.get_section_sources("run.plan", "coding.bootstrap")

    assert len(section_sources) == 6
    populated = [s for s in section_sources if s.source_kind is not None]
    assert len(populated) == 6
    assert all(s.source_kind == VariableSourceKind.PROVIDER for s in populated)


def test_token_estimate() -> None:
    """Verify token estimation formula."""
    text = "a" * 100
    estimate = token_estimate(text)

    assert estimate == 25  # 100 chars / 4


def test_detect_anomalies_repo_profile_provider_source_no_false_positive() -> None:
    """Provider source with 'profile' keyword should NOT trigger has_repo_profile."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(
            key="provider",
            source_kind=VariableSourceKind.PROVIDER,
            source_ref="get_profile_config",  # Has 'profile' keyword but is PROVIDER
        ),
    )
    section_order: tuple[str, ...] = ("provider",)

    anomalies = detect_anomalies("text", section_sources, section_order)

    # Should NOT trigger because source_kind is not FILE
    assert anomalies.has_repo_profile is False


def test_detect_anomalies_policy_overlay_command_source_no_false_positive() -> None:
    """Command source with 'policy' keyword should NOT trigger flag."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(
            key="cmd",
            source_kind=VariableSourceKind.COMMAND,
            source_ref="policy-check.sh",  # Has 'policy' keyword but is COMMAND
        ),
    )
    section_order: tuple[str, ...] = ("cmd",)

    anomalies = detect_anomalies("text", section_sources, section_order)

    # Should NOT trigger because source_kind is not FILE
    assert anomalies.has_project_policy_overlay is False


def test_detect_anomalies_duplicate_in_variable_provenance() -> None:
    """Duplicates across section and variable provenance should be detected."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(key="section1", source_ref="shared_file.md"),
    )
    section_order: tuple[str, ...] = ("section1",)
    variable_provenance: tuple[PromptVariableProvenance, ...] = (
        PromptVariableProvenance(
            variable="var1",
            source_kind=VariableSourceKind.FILE,
            resolved_from="shared_file.md",  # Same as section source
            value_preview="content",
        ),
    )

    anomalies = detect_anomalies(
        "text", section_sources, section_order, variable_provenance
    )

    # Should detect duplicate across section and variable
    assert anomalies.has_duplicate_material is True


def test_detect_anomalies_no_duplicate_with_different_sources() -> None:
    """Different sources in section and variable provenance should not trigger."""
    section_sources: tuple[SectionSourceProvenance, ...] = (
        SectionSourceProvenance(key="section1", source_ref="file1.md"),
    )
    section_order: tuple[str, ...] = ("section1",)
    variable_provenance: tuple[PromptVariableProvenance, ...] = (
        PromptVariableProvenance(
            variable="var1",
            source_kind=VariableSourceKind.FILE,
            resolved_from="file2.md",  # Different from section source
            value_preview="content",
        ),
    )

    anomalies = detect_anomalies(
        "text", section_sources, section_order, variable_provenance
    )

    # Should NOT detect duplicate
    assert anomalies.has_duplicate_material is False


# --- Integration tests: section sources from real recipes ---


def test_get_section_sources_run_plan() -> None:
    """Verify run.plan recipe yields section sources with provider attribution."""
    manifest = PromptManifest.load_default()
    sources = manifest.get_section_sources("run.plan", "coding.bootstrap")

    assert len(sources) > 0
    assert all(
        s.source_kind == VariableSourceKind.PROVIDER for s in sources
    ), "run.plan sections should have provider source attribution"


def test_get_section_sources_review_default() -> None:
    """Verify review.default recipe yields section sources with provider attribution."""
    manifest = PromptManifest.load_default()
    sources = manifest.get_section_sources("review.default", "first.bootstrap")

    assert len(sources) > 0
    assert all(
        s.source_kind == VariableSourceKind.PROVIDER for s in sources
    ), "review.default sections should have provider source attribution"


def test_get_section_sources_governance_scan_template() -> None:
    """Verify governance.scan template recipe yields material_catalog as sources.

    Template-based recipes have no variants, but should return
    material_catalog entries with FILE source_kind and material paths.
    """
    manifest = PromptManifest.load_default()
    sources = manifest.get_section_sources("governance.scan", "")

    assert len(sources) > 0, (
        "Expected governance.scan template recipe to yield "
        "material_catalog as section sources"
    )
    for s in sources:
        assert s.source_kind == VariableSourceKind.FILE, (
            f"Expected FILE source_kind for governance.scan section {s.key}, "
            f"got {s.source_kind}"
        )
        assert (
            s.source_ref is not None
        ), f"Expected source_ref for governance.scan section '{s.key}'"


def test_collect_run_plan_provenance_with_sources() -> None:
    """Verify collect_dry_run_provenance for run.plan includes provider sources."""
    manifest = PromptManifest.load_default()
    provenance = collect_dry_run_provenance(
        manifest,
        recipe_key="run.plan",
        variant_key="coding.bootstrap",
        rendered_text="run prompt content",
    )

    assert provenance.recipe_key == "run.plan"
    assert provenance.variant_key == "coding.bootstrap"
    assert len(provenance.section_order) > 0
    assert len(provenance.section_sources) > 0
    assert all(
        s.source_kind == VariableSourceKind.PROVIDER
        for s in provenance.section_sources
    )


def test_collect_review_default_provenance_with_sources() -> None:
    """Verify collect_dry_run_provenance for review.default includes provider sources."""
    manifest = PromptManifest.load_default()
    provenance = collect_dry_run_provenance(
        manifest,
        recipe_key="review.default",
        variant_key="first.bootstrap",
        rendered_text="review prompt content",
    )

    assert provenance.recipe_key == "review.default"
    assert provenance.variant_key == "first.bootstrap"
    assert len(provenance.section_order) > 0
    assert len(provenance.section_sources) > 0
    assert all(
        s.source_kind == VariableSourceKind.PROVIDER
        for s in provenance.section_sources
    )


def test_collect_governance_scan_provenance() -> None:
    """Verify collect_dry_run_provenance for governance.scan (template recipe).

    Template recipes (governance.scan) use material_catalog as section sources.
    All material_catalog entries should have FILE source_kind and valid paths.
    """
    manifest = PromptManifest.load_default()
    provenance = collect_dry_run_provenance(
        manifest,
        recipe_key="governance.scan",
        variant_key="",
        rendered_text="governance prompt content",
    )

    assert provenance.recipe_key == "governance.scan"
    assert provenance.variant_key == ""
    # Template recipes have no section_order (no variants),
    # but should have section_sources from material_catalog
    assert (
        len(provenance.section_sources) > 0
    ), "Expected governance.scan to yield material_catalog section sources"
    for section in provenance.section_sources:
        assert section.source_kind == VariableSourceKind.FILE, (
            f"Expected FILE source_kind for governance.scan section "
            f"'{section.key}', got {section.source_kind}"
        )
        assert (
            section.source_ref is not None
        ), f"Expected source_ref for governance.scan section '{section.key}'"


def test_collect_provenance_with_warnings() -> None:
    """Verify warnings are carried through provenance."""
    manifest = PromptManifest.load_default()
    provenance = collect_dry_run_provenance(
        manifest,
        recipe_key="plan.default",
        variant_key="first.bootstrap",
        rendered_text="test",
        warnings=("missing provider: custom_section",),
    )

    assert len(provenance.warnings) == 1
    assert "missing provider: custom_section" in provenance.warnings
