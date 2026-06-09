from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vibe3.services.handoff.resolution import resolve_handoff_target


def _make_git_client(git_common: str, worktree_root: str) -> MagicMock:
    client = MagicMock()
    client.get_git_common_dir.return_value = git_common
    client.get_worktree_root.return_value = worktree_root
    client.find_worktree_path_for_branch.return_value = None
    return client


# --- resolve_handoff_target ---


def test_resolve_handoff_target_shared_artifact(tmp_path: Path) -> None:
    """@key resolves to git_common/vibe3/handoff/<key>."""
    artifact = tmp_path / "vibe3" / "handoff" / "task-123" / "run.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("content")

    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))
    result = resolve_handoff_target("@task-123/run.md", git_client=client)
    assert result == artifact


def test_resolve_handoff_target_shared_artifact_not_found(tmp_path: Path) -> None:
    """@key raises FileNotFoundError when artifact is missing."""
    client = _make_git_client(str(tmp_path), str(tmp_path / "wt"))
    with pytest.raises(FileNotFoundError):
        resolve_handoff_target("@missing/run.md", git_client=client)


def test_resolve_handoff_target_absolute_path(tmp_path: Path) -> None:
    """Absolute path is returned directly (debug fallback)."""
    target_file = tmp_path / "file.md"
    target_file.write_text("content")

    client = _make_git_client(str(tmp_path), str(tmp_path))
    result = resolve_handoff_target(str(target_file), git_client=client)
    assert result == target_file


def test_resolve_handoff_target_canonical_ref_current_worktree(
    tmp_path: Path,
) -> None:
    """Relative path resolves to current worktree when no branch given."""
    ref_file = tmp_path / "docs" / "report.md"
    ref_file.parent.mkdir(parents=True)
    ref_file.write_text("content")

    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path))
    result = resolve_handoff_target("docs/report.md", git_client=client)
    assert result == ref_file


def test_resolve_handoff_target_canonical_ref_with_branch(tmp_path: Path) -> None:
    """Relative path resolves to branch worktree when --branch given."""
    branch_wt = tmp_path / "wt-branch"
    ref_file = branch_wt / "docs" / "report.md"
    ref_file.parent.mkdir(parents=True)
    ref_file.write_text("content")

    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path / "wt-main"))
    client.find_worktree_path_for_branch.return_value = branch_wt
    result = resolve_handoff_target(
        "docs/report.md", branch="task/issue-99", git_client=client
    )
    assert result == ref_file


def test_resolve_handoff_target_not_found_raises(tmp_path: Path) -> None:
    """Unresolvable target raises FileNotFoundError."""
    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path / "wt"))
    with pytest.raises(FileNotFoundError):
        resolve_handoff_target("docs/nonexistent.md", git_client=client)


def test_resolve_handoff_target_branch_strict_no_fallback(tmp_path: Path) -> None:
    """When --branch given, file missing from branch worktree → error."""
    branch_wt = tmp_path / "wt-branch"
    branch_wt.mkdir()
    # File exists in CWD but NOT in branch worktree
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "report.md").write_text("wrong-flow-content")

    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path))
    client.find_worktree_path_for_branch.return_value = branch_wt

    with pytest.raises(FileNotFoundError, match="File not found in branch"):
        resolve_handoff_target(
            "docs/report.md", branch="task/issue-99", git_client=client
        )


def test_resolve_handoff_target_branch_no_worktree_raises(tmp_path: Path) -> None:
    """When --branch given but worktree missing → error."""
    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path / "wt"))
    client.find_worktree_path_for_branch.return_value = None

    with pytest.raises(FileNotFoundError, match="No worktree found for branch"):
        resolve_handoff_target(
            "docs/report.md", branch="task/issue-99", git_client=client
        )


# --- @indicate alias resolution ---


def test_resolve_handoff_target_at_indicate_alias(tmp_path: Path) -> None:
    """@indicate resolves via flow_state.indicate_ref."""
    from unittest.mock import patch

    # Create the artifact file
    artifact = tmp_path / "docs" / "plans" / "issue-123-indicate.md"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("indicate content")

    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path))
    client.get_current_branch.return_value = "task/issue-123"
    client.find_worktree_path_for_branch.return_value = tmp_path

    # Mock SQLiteClient to return flow_state with indicate_ref
    mock_flow_state = {"indicate_ref": "docs/plans/issue-123-indicate.md"}
    with patch("vibe3.clients.SQLiteClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_flow_state.return_value = mock_flow_state
        mock_client_class.return_value = mock_client

        result = resolve_handoff_target(
            "@indicate", branch="task/issue-123", git_client=client
        )
        assert result == artifact


def test_resolve_handoff_target_at_indicate_not_set(tmp_path: Path) -> None:
    """@indicate raises FileNotFoundError when indicate_ref not set."""
    from unittest.mock import patch

    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path))
    client.get_current_branch.return_value = "task/issue-123"

    # Mock SQLiteClient to return flow_state without indicate_ref
    mock_flow_state = {"plan_ref": "docs/plans/plan.md"}  # No indicate_ref
    with patch("vibe3.clients.SQLiteClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_flow_state.return_value = mock_flow_state
        mock_client_class.return_value = mock_client

        with pytest.raises(FileNotFoundError, match="No indicate_ref recorded"):
            resolve_handoff_target(
                "@indicate", branch="task/issue-123", git_client=client
            )


def test_resolve_handoff_target_at_indicate_self_referential(tmp_path: Path) -> None:
    """@indicate rejects self-referential alias to prevent infinite recursion."""
    from unittest.mock import patch

    client = _make_git_client(str(tmp_path / ".git"), str(tmp_path))
    client.get_current_branch.return_value = "task/issue-123"

    # Mock SQLiteClient to return flow_state with self-referential indicate_ref
    mock_flow_state = {"indicate_ref": "@indicate"}  # Self-referential!
    with patch("vibe3.clients.SQLiteClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.get_flow_state.return_value = mock_flow_state
        mock_client_class.return_value = mock_client

        with pytest.raises(ValueError, match="self-referential alias"):
            resolve_handoff_target(
                "@indicate", branch="task/issue-123", git_client=client
            )


# --- @vibe/ namespace resolution ---


def test_resolve_vibe_material_in_vibe3_repo(tmp_path: Path) -> None:
    """@vibe/<path> resolves when current repo is vibe3."""
    from unittest.mock import patch

    # Create a file in the vibe3 installation
    material_file = tmp_path / "skills" / "test-skill" / "SKILL.md"
    material_file.parent.mkdir(parents=True)
    material_file.write_text("skill content")

    # Mock cwd to simulate running from vibe3 repo
    with patch("pathlib.Path.cwd", return_value=tmp_path):
        # Create pyproject.toml to identify as vibe3
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[project]\nname = "vibe3"\n')

        result = resolve_handoff_target("@vibe/skills/test-skill/SKILL.md")
        assert result == material_file


def test_resolve_vibe_material_with_explicit_vibe_dir(tmp_path: Path) -> None:
    """@vibe/<path> resolves with explicit --vibe-dir."""
    # Create a vibe installation directory
    vibe_root = tmp_path / "vibe3-install"
    material_file = vibe_root / "skills" / "test-skill" / "SKILL.md"
    material_file.parent.mkdir(parents=True)
    material_file.write_text("skill content")

    result = resolve_handoff_target(
        "@vibe/skills/test-skill/SKILL.md", vibe_dir=str(vibe_root)
    )
    assert result == material_file


def test_resolve_vibe_material_fallback_global(tmp_path: Path) -> None:
    """@vibe/<path> falls back to ~/.vibe when not in vibe3 repo."""
    from unittest.mock import patch

    # Create a global installation
    global_vibe = tmp_path / "home" / ".vibe"
    material_file = global_vibe / "skills" / "test-skill" / "SKILL.md"
    material_file.parent.mkdir(parents=True)
    material_file.write_text("skill content")

    # Mock Path.home() to return our temp home
    with patch("pathlib.Path.home", return_value=tmp_path / "home"):
        # Mock cwd to return non-vibe3 directory
        with patch("pathlib.Path.cwd", return_value=tmp_path / "other"):
            result = resolve_handoff_target("@vibe/skills/test-skill/SKILL.md")
            assert result == material_file


def test_resolve_vibe_material_not_found(tmp_path: Path) -> None:
    """@vibe/<path> raises FileNotFoundError when file does not exist."""
    vibe_root = tmp_path / "vibe3-install"
    vibe_root.mkdir()

    with pytest.raises(FileNotFoundError, match="Material not found"):
        resolve_handoff_target(
            "@vibe/skills/nonexistent/SKILL.md", vibe_dir=str(vibe_root)
        )


def test_resolve_vibe_material_not_a_file(tmp_path: Path) -> None:
    """@vibe/<path> raises FileNotFoundError when path is a directory."""
    vibe_root = tmp_path / "vibe3-install"
    material_dir = vibe_root / "skills" / "test-skill"
    material_dir.mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="Not a file"):
        resolve_handoff_target("@vibe/skills/test-skill", vibe_dir=str(vibe_root))


def test_resolve_vibe_material_vibe_installation_not_found(tmp_path: Path) -> None:
    """@vibe/<path> raises FileNotFoundError when vibe installation not found."""
    from unittest.mock import patch

    # Mock cwd to return non-vibe3 directory
    # Mock Path.home() to return temp without .vibe
    with patch("pathlib.Path.cwd", return_value=tmp_path / "other"):
        with patch("pathlib.Path.home", return_value=tmp_path / "home"):
            with pytest.raises(
                FileNotFoundError, match="Cannot find vibe3 installation"
            ):
                resolve_handoff_target("@vibe/skills/test-skill/SKILL.md")
