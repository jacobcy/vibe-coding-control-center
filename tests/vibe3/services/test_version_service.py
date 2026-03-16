"""Tests for Version service."""
import tempfile
from pathlib import Path

import pytest

from vibe3.services.version_service import VersionService
from vibe3.models.pr import VersionBumpType


@pytest.fixture
def version_service() -> VersionService:
    """Create version service fixture."""
    return VersionService()


@pytest.fixture
def version_service_with_file() -> VersionService:
    """Create version service with temporary VERSION file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".VERSION", delete=False) as f:
        f.write("1.2.3\n")
        version_file = Path(f.name)

    service = VersionService(version_file=version_file)
    yield service

    # Cleanup
    version_file.unlink()


def test_get_current_version_from_file(version_service_with_file: VersionService) -> None:
    """Test reading version from VERSION file."""
    version = version_service_with_file.get_current_version()
    assert version == "1.2.3"


def test_get_current_version_file_not_found() -> None:
    """Test error when VERSION file doesn't exist."""
    service = VersionService(version_file="/nonexistent/VERSION")
    with pytest.raises(FileNotFoundError, match="VERSION file not found"):
        service.get_current_version()


def test_calculate_bump_reads_from_file(version_service_with_file: VersionService) -> None:
    """Test calculate_bump reads from VERSION file when current_version is None."""
    response = version_service_with_file.calculate_bump(group="feature")

    assert response.current_version == "1.2.3"
    assert response.bump_type == VersionBumpType.MINOR
    assert response.next_version == "1.3.0"


def test_feature_bumps_minor(version_service: VersionService) -> None:
    """Test feature group triggers minor bump."""
    response = version_service.calculate_bump(group="feature", current_version="0.1.0")

    assert response.bump_type == VersionBumpType.MINOR
    assert response.next_version == "0.2.0"
    assert "minor" in response.reason.lower()


def test_bug_bumps_patch(version_service: VersionService) -> None:
    """Test bug group triggers patch bump."""
    response = version_service.calculate_bump(group="bug", current_version="0.1.0")

    assert response.bump_type == VersionBumpType.PATCH
    assert response.next_version == "0.1.1"
    assert "patch" in response.reason.lower()


def test_docs_no_bump(version_service: VersionService) -> None:
    """Test docs group triggers no bump."""
    response = version_service.calculate_bump(group="docs", current_version="0.1.0")

    assert response.bump_type == VersionBumpType.NONE
    assert response.next_version == "0.1.0"


def test_chore_no_bump(version_service: VersionService) -> None:
    """Test chore group triggers no bump."""
    response = version_service.calculate_bump(group="chore", current_version="0.1.0")

    assert response.bump_type == VersionBumpType.NONE
    assert response.next_version == "0.1.0"


def test_unknown_group_defaults_to_patch(version_service: VersionService) -> None:
    """Test unknown group defaults to patch."""
    response = version_service.calculate_bump(group="unknown", current_version="0.1.0")

    assert response.bump_type == VersionBumpType.PATCH
    assert response.next_version == "0.1.1"


def test_major_bump(version_service: VersionService) -> None:
    """Test major version bump."""
    response = version_service.calculate_bump(group="feature", current_version="1.2.3")

    assert response.next_version == "1.3.0"


def test_patch_bump_resets_patch(version_service: VersionService) -> None:
    """Test minor bump resets patch to 0."""
    response = version_service.calculate_bump(group="feature", current_version="0.1.5")

    assert response.next_version == "0.2.0"


def test_invalid_version_format(version_service: VersionService) -> None:
    """Test invalid version format raises error."""
    with pytest.raises(ValueError, match="Invalid version format"):
        version_service.calculate_bump(group="feature", current_version="invalid")