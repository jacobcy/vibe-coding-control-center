"""Version service implementation."""
from pathlib import Path

from vibe3.models.pr import VersionBumpResponse, VersionBumpType


class VersionService:
    """Service for version management."""

    def __init__(self, version_file: str | Path | None = None) -> None:
        """Initialize version service.

        Args:
            version_file: Path to VERSION file (default: <project_root>/VERSION)
        """
        if version_file is None:
            # Find project root (where VERSION file should be)
            project_root = Path(__file__).parent.parent.parent.parent.parent
            version_file = project_root / "VERSION"
        self.version_file = Path(version_file)

    def get_current_version(self) -> str:
        """Get current version from VERSION file.

        Returns:
            Current version string

        Raises:
            FileNotFoundError: If VERSION file doesn't exist
            ValueError: If VERSION file is empty or invalid
        """
        if not self.version_file.exists():
            raise FileNotFoundError(f"VERSION file not found: {self.version_file}")

        version = self.version_file.read_text().strip()
        if not version:
            raise ValueError(f"VERSION file is empty: {self.version_file}")

        return version

    def calculate_bump(
        self,
        group: str | None = None,
        current_version: str | None = None,
    ) -> VersionBumpResponse:
        """Calculate version bump based on task group.

        Args:
            group: Task group (feature/bug/docs/chore)
            current_version: Current version (semver). If None, read from VERSION file.

        Returns:
            Version bump response

        Raises:
            ValueError: If version format is invalid
            FileNotFoundError: If VERSION file doesn't exist
                (when current_version is None)
        """
        # Read version from file if not provided
        if current_version is None:
            current_version = self.get_current_version()

        # Determine bump type based on group
        if group == "feature":
            bump_type = VersionBumpType.MINOR
            reason = "Feature tasks trigger minor version bump"
        elif group == "bug":
            bump_type = VersionBumpType.PATCH
            reason = "Bug fixes trigger patch version bump"
        elif group in ("docs", "chore"):
            bump_type = VersionBumpType.NONE
            reason = "Docs/chore tasks do not trigger version bump by default"
        else:
            # Default to patch for unknown groups
            bump_type = VersionBumpType.PATCH
            reason = "Default to patch version bump"

        next_version = self._calculate_next_version(current_version, bump_type)

        return VersionBumpResponse(
            current_version=current_version,
            bump_type=bump_type,
            next_version=next_version,
            reason=reason,
        )

    def _calculate_next_version(self, current: str, bump_type: VersionBumpType) -> str:
        """Calculate next version based on bump type.

        Args:
            current: Current version (semver)
            bump_type: Version bump type

        Returns:
            Next version

        Raises:
            ValueError: If version format is invalid
        """
        if bump_type == VersionBumpType.NONE:
            return current

        parts = current.split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid version format: {current}")

        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

        if bump_type == VersionBumpType.MAJOR:
            major += 1
            minor = 0
            patch = 0
        elif bump_type == VersionBumpType.MINOR:
            minor += 1
            patch = 0
        elif bump_type == VersionBumpType.PATCH:
            patch += 1

        return f"{major}.{minor}.{patch}"
