"""Governance material resolution functions.

This module provides functions for loading and resolving governance materials
from the prompt manifest. Moved from roles/governance.py to avoid circular
dependencies (Issue #3194).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from vibe3.models import OrchestraConfig
from vibe3.prompts import PromptManifest, PromptMaterialSpec, PromptRecipeDefinition


def load_governance_material_catalog() -> tuple[PromptMaterialSpec, ...]:
    """Load the governance material catalog from prompt manifest.

    Returns:
        Tuple of PromptMaterialSpec objects for governance materials.
    """
    recipe_def = _load_governance_recipe_definition()
    if not recipe_def.loaded_definition:
        raise ValueError("governance.scan recipe not properly loaded")
    catalog = recipe_def.loaded_definition.material_catalog
    if not catalog:
        raise ValueError("governance.scan recipe requires material_catalog")
    return catalog


def resolve_governance_material(
    config: OrchestraConfig,
    execution_count: int,
) -> str:
    """Resolve governance material based on execution count.

    Uses execution_count to rotate through the material catalog, ensuring
    each governance scan uses a different material in sequence.

    Args:
        config: Orchestra configuration (unused but kept for API compatibility)
        execution_count: Execution counter for material rotation

    Returns:
        Material name string (e.g., "supervisor/governance/cron-supervisor.md")
    """
    _ = config
    catalog = load_governance_material_catalog()
    return catalog[execution_count % len(catalog)].name


def build_governance_execution_name(
    tick_count: int, material: str | None = None
) -> str:
    """Build unique execution name for a governance scan tick.

    If material is provided, extracts the material slug (stem) and uses it
    as the execution name prefix for material-specific log paths.

    Args:
        tick_count: Current tick count
        material: Optional material path
            (e.g., "supervisor/governance/cron-supervisor.md")

    Returns:
        Execution name string
            (e.g., "cron-supervisor-20260627-010215-t8" with material,
                   "vibe3-governance-scan-20260627-010215-t8" without)
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if material:
        # Extract material slug from path
        # (e.g. "supervisor/governance/cron-supervisor.md" -> "cron-supervisor")
        material_slug = Path(material).stem
        # New format: {material_slug}-{timestamp}-t{tick}
        return f"{material_slug}-{timestamp}-t{tick_count}"
    # Backward compat: keep legacy prefix when no material info
    return f"vibe3-governance-scan-{timestamp}-t{tick_count}"


def _load_governance_recipe_definition() -> PromptRecipeDefinition:
    """Load the governance.scan recipe definition."""
    return PromptManifest.load_default().recipe("governance.scan")
