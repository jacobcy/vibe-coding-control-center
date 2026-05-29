"""Adapter manifest model for declaring distribution resources."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AdapterResource(BaseModel):
    """A single resource provided by an adapter."""

    type: Literal["skill", "policy", "workflow", "supervisor", "report", "config"]
    name: str = Field(description="Unique name for this resource within its type")
    path: str = Field(description="Relative path from repo root")

    model_config = {"frozen": True}


class AdapterManifest(BaseModel):
    """Manifest declaring what an adapter provides.

    An adapter is a distribution of vibe3 resources (skills, policies,
    workflows, supervisor templates, etc.) that can be explicitly enabled
    by selecting a profile.

    Attributes:
        name: Unique adapter identifier (e.g., 'vibe-center')
        version: Semantic version of this adapter
        description: Human-readable description
        resources: List of resources this adapter provides
    """

    name: str = Field(min_length=1, description="Unique adapter identifier")
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$", description="SemVer version")
    description: str = Field(default="", description="Adapter description")
    resources: list[AdapterResource] = Field(default_factory=list)

    model_config = {"frozen": True}

    def model_post_init(self, __context: object) -> None:
        """Build resource index for O(1) lookup after validation."""
        self._resource_index: dict[tuple[str, str], AdapterResource] = {}
        for r in self.resources:
            key = (r.type, r.name)
            self._resource_index[key] = r

    def get_resources_by_type(self, resource_type: str) -> list[AdapterResource]:
        """Get all resources of a specific type.

        Args:
            resource_type: One of 'skill', 'policy', 'workflow', 'supervisor', etc.

        Returns:
            List of resources matching the type
        """
        return [r for r in self.resources if r.type == resource_type]

    def get_resource(self, resource_type: str, name: str) -> AdapterResource | None:
        """Get a specific resource by type and name.

        Args:
            resource_type: Resource type
            name: Resource name

        Returns:
            Matching resource or None if not found
        """
        key = (resource_type, name)
        return self._resource_index.get(key)

    @field_validator("resources")
    @classmethod
    def validate_unique_resources(
        cls, v: list[AdapterResource]
    ) -> list[AdapterResource]:
        """Ensure resources have unique type+name combinations."""
        seen = set()
        for r in v:
            key = (r.type, r.name)
            if key in seen:
                raise ValueError(f"Duplicate resource: {r.type}/{r.name}")
            seen.add(key)
        return v
