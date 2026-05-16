"""Asset manifest schema for global assets."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from vibe3.assets.constants import ASSET_TYPES


class AssetManifest(BaseModel):
    """Schema for global assets manifest."""

    version: str = Field(
        description="Assets manifest version (semver)",
        pattern=r"^\d+\.\d+\.\d+$",
    )
    checksums: dict[str, str] = Field(
        default_factory=dict,
        description="Relative paths to SHA256 checksums",
    )

    @field_validator("checksums")
    @classmethod
    def validate_checksum_paths(cls, v: dict[str, str]) -> dict[str, str]:
        """Ensure checksum paths are within valid asset types."""
        valid_prefixes = set(ASSET_TYPES)
        return {
            path: checksum
            for path, checksum in v.items()
            if path.split("/")[0] in valid_prefixes
        }

    def save(self, path: Path) -> None:
        """Save manifest to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.model_dump(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "AssetManifest":
        """Load manifest from JSON file."""
        data = json.loads(path.read_text())
        return cls.model_validate(data)
