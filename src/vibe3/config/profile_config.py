"""Profile-based resource resolution.

Connects profile selection to adapter resource lookup,
providing a unified API for accessing policy/skill/workflow paths.
"""

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from vibe3.config.adapter_manifest import AdapterManifest


class ProfileConfig(BaseModel):
    """Configuration for a specific profile's resource resolution.

    Maps profile name to adapter and provides resource lookup methods.
    """

    profile: str = Field(default="minimal", description="Profile name")

    def _get_adapter(self) -> "AdapterManifest | None":
        """Get adapter for current profile.

        Returns:
            Adapter manifest or None if profile has no adapter
        """
        from vibe3.adapters import get_adapter

        # Map profile names to adapter names
        adapter_map: dict[str, str] = {
            "vibe-center": "vibe-center",
            # Future: "github-flow": "github-flow-adapter",
        }

        adapter_name = adapter_map.get(self.profile)
        if adapter_name:
            return get_adapter(adapter_name)
        return None

    def get_policy_path(self, name: str) -> str | None:
        """Get path to a policy file.

        Args:
            name: Policy name (e.g., 'plan', 'run', 'review')

        Returns:
            Relative path or None if not found
        """
        adapter = self._get_adapter()
        if not adapter:
            return None

        resource = adapter.get_resource("policy", name)
        return resource.path if resource else None

    def get_skill_path(self, name: str) -> str | None:
        """Get path to a skill SKILL.md.

        Args:
            name: Skill name (e.g., 'vibe-commit')

        Returns:
            Relative path or None if not found
        """
        adapter = self._get_adapter()
        if not adapter:
            return None

        resource = adapter.get_resource("skill", name)
        return resource.path if resource else None

    def get_supervisor_path(self, name: str) -> str | None:
        """Get path to a supervisor template.

        Args:
            name: Template name (e.g., 'apply')

        Returns:
            Relative path or None if not found
        """
        adapter = self._get_adapter()
        if not adapter:
            return None

        resource = adapter.get_resource("supervisor", name)
        return resource.path if resource else None

    def get_workflow_path(self, name: str) -> str | None:
        """Get path to a workflow.

        Args:
            name: Workflow name

        Returns:
            Relative path or None if not found
        """
        adapter = self._get_adapter()
        if not adapter:
            return None

        resource = adapter.get_resource("workflow", name)
        return resource.path if resource else None
