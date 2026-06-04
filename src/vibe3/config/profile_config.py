"""Profile-based resource resolution.

Connects profile selection to adapter resource lookup,
providing a unified API for accessing policy/skill/workflow paths.
"""

from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from vibe3.models.adapter_manifest import AdapterManifest

AdapterResolver = Callable[[str], "AdapterManifest | None"]


class ProfileConfig(BaseModel):
    """Configuration for a specific profile's resource resolution.

    Maps profile name to adapter and provides resource lookup methods.

    Attributes:
        profile: Profile name (vibe-center, minimal, etc.)
        adapter_resolver: Optional callback to resolve adapters by name.
            If not provided, adapter lookup is disabled.
    """

    profile: str = Field(default="minimal", description="Profile name")
    adapter_resolver: Callable[..., Any] | None = Field(
        default=None, description="Callback to resolve adapters", exclude=True
    )

    def _get_adapter(self) -> "AdapterManifest | None":
        """Get adapter for current profile.

        Returns:
            Adapter manifest or None if profile has no adapter or no resolver
        """
        if not self.adapter_resolver:
            return None

        # Map profile names to adapter names
        adapter_map: dict[str, str] = {
            "vibe-center": "vibe-center",
            "github-flow": "github-flow",
        }

        adapter_name = adapter_map.get(self.profile)
        if adapter_name:
            result = self.adapter_resolver(adapter_name)
            from vibe3.models.adapter_manifest import AdapterManifest

            return result if isinstance(result, AdapterManifest) else None
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
