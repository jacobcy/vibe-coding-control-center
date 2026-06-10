"""Tests for scan service functions."""

import yaml

from vibe3.roles.scan_service import (
    extract_material_description,
    fetch_supervisor_candidates,
    validate_governance_material_consistency,
)


class TestExtractMaterialDescription:
    """Tests for material description extraction."""

    def test_extracts_title_from_markdown(self, tmp_path, monkeypatch):
        """Extract title from material name via material_loader."""
        gov_dir = tmp_path / "supervisor" / "governance"
        gov_dir.mkdir(parents=True)
        (gov_dir / "test-material.md").write_text(
            "# Test Material 治理材料\n\nSome content\n"
        )
        monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(tmp_path))
        external = tmp_path / "external-repo"
        external.mkdir()
        monkeypatch.chdir(external)

        description = extract_material_description(
            "supervisor/governance/test-material.md"
        )
        assert description == "Test Material 治理材料"

    def test_fallback_to_filename_without_title(self, tmp_path, monkeypatch):
        """Fallback to material name when no title in file."""
        gov_dir = tmp_path / "supervisor" / "governance"
        gov_dir.mkdir(parents=True)
        (gov_dir / "no-title.md").write_text("Some content without title\n")
        monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(tmp_path))
        external = tmp_path / "external-repo"
        external.mkdir()
        monkeypatch.chdir(external)

        description = extract_material_description("supervisor/governance/no-title.md")
        assert "no-title.md" in description

    def test_handles_missing_file(self, tmp_path, monkeypatch):
        """Handling of missing material file."""
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.setenv("VIBE3_RUNTIME_ASSETS_ROOT", str(empty))
        external = tmp_path / "external-repo"
        external.mkdir()
        monkeypatch.chdir(external)

        description = extract_material_description(
            "supervisor/governance/nonexistent.md"
        )
        assert "nonexistent.md" in description


class TestFetchSupervisorCandidates:
    """Tests for supervisor candidate fetching."""

    def test_filters_by_labels(self):
        """Test filtering issues by supervisor + state/handoff labels."""
        from unittest.mock import MagicMock

        mock_github = MagicMock()
        mock_github.list_issues.return_value = [
            {
                "number": 123,
                "title": "Test Issue",
                "labels": [{"name": "supervisor"}, {"name": "state/handoff"}],
            },
            {
                "number": 456,
                "title": "No Handoff",
                "labels": [{"name": "supervisor"}],
            },
        ]

        total_scanned, candidates = fetch_supervisor_candidates(
            mock_github, "owner/repo"
        )

        # Should return total scanned count
        assert total_scanned == 2
        # Should only return issue with both labels
        assert len(candidates) == 1
        assert candidates[0]["number"] == 123

    def test_returns_empty_list_on_error(self):
        """Test returns empty tuple on GitHub error."""
        from unittest.mock import MagicMock

        mock_github = MagicMock()
        mock_github.list_issues.side_effect = Exception("API Error")

        total_scanned, candidates = fetch_supervisor_candidates(
            mock_github, "owner/repo"
        )
        assert total_scanned == 0
        assert candidates == []

    def test_queries_100_issues_not_50(self):
        """Test that fetch_supervisor_candidates queries 100 issues (Issue #803).

        Previously queried only 50 issues, causing dry-run to miss candidates.
        """
        from unittest.mock import MagicMock

        mock_github = MagicMock()
        mock_github.list_issues.return_value = []

        total_scanned, candidates = fetch_supervisor_candidates(
            mock_github, "owner/repo"
        )

        # Verify limit parameter is 100 (not 50)
        mock_github.list_issues.assert_called_once()
        call_args = mock_github.list_issues.call_args
        assert call_args.kwargs.get("limit") == 100
        # Empty results
        assert total_scanned == 0
        assert candidates == []


def _make_recipes_yaml(materials: list[dict]) -> str:
    """Build a minimal prompt-recipes.yaml content with governance.scan recipe."""
    catalog = []
    for mat in materials:
        catalog.append(
            {
                "name": mat["name"],
                "source": {"kind": "file", "path": mat["name"]},
            }
        )
    data = {
        "recipes": {
            "governance.scan": {
                "kind": "template_recipe",
                "template_key": "orchestra.governance.plan",
                "material_catalog": catalog,
            }
        }
    }
    return yaml.dump(data)


def _make_adapter(supervisor_resources: list[dict]):
    """Build a minimal AdapterManifest with given supervisor resources."""
    from vibe3.models.adapter_manifest import AdapterManifest, AdapterResource

    resources = [
        AdapterResource(type="supervisor", name=r["name"], path=r["path"])
        for r in supervisor_resources
    ]
    return AdapterManifest(
        name="test-adapter",
        version="1.0.0",
        description="Test adapter",
        resources=resources,
    )


class TestValidateGovernanceMaterialConsistency:
    """Tests for governance material consistency validation."""

    def test_all_consistent(self, tmp_path):
        """Valid adapter + valid recipes + existing files -> empty issues."""
        material_name = "supervisor/governance/test-material.md"
        material_file = tmp_path / material_name
        material_file.parent.mkdir(parents=True, exist_ok=True)
        material_file.write_text("# Test\n")

        recipes_file = tmp_path / "prompt-recipes.yaml"
        recipes_file.write_text(_make_recipes_yaml([{"name": material_name}]))

        adapter = _make_adapter([{"name": "test-material", "path": material_name}])

        issues = validate_governance_material_consistency(
            adapter=adapter, recipes_path=recipes_file, repo_root=tmp_path
        )
        assert issues == []

    def test_missing_adapter_registration(self, tmp_path):
        """Material in catalog but no adapter resource -> missing_adapter issue."""
        material_name = "supervisor/governance/ghost.md"
        material_file = tmp_path / material_name
        material_file.parent.mkdir(parents=True, exist_ok=True)
        material_file.write_text("# Ghost\n")

        recipes_file = tmp_path / "prompt-recipes.yaml"
        recipes_file.write_text(_make_recipes_yaml([{"name": material_name}]))

        # Adapter has NO supervisor resources
        adapter = _make_adapter([])

        issues = validate_governance_material_consistency(
            adapter=adapter, recipes_path=recipes_file, repo_root=tmp_path
        )
        assert len(issues) == 1
        assert issues[0]["type"] == "missing_adapter"
        assert material_name in issues[0]["message"]

    def test_missing_file(self, tmp_path):
        """Material in catalog and adapter but file doesn't exist -> missing_file."""
        material_name = "supervisor/governance/nonexistent.md"

        recipes_file = tmp_path / "prompt-recipes.yaml"
        recipes_file.write_text(_make_recipes_yaml([{"name": material_name}]))

        adapter = _make_adapter([{"name": "nonexistent", "path": material_name}])

        issues = validate_governance_material_consistency(
            adapter=adapter, recipes_path=recipes_file, repo_root=tmp_path
        )
        assert len(issues) == 1
        assert issues[0]["type"] == "missing_file"
        assert material_name in issues[0]["message"]

    def test_orphaned_adapter_registration(self, tmp_path):
        """Adapter has supervisor/governance/ resource not in catalog -> orphaned."""
        # Catalog only has "known.md"
        known_name = "supervisor/governance/known.md"
        known_file = tmp_path / known_name
        known_file.parent.mkdir(parents=True, exist_ok=True)
        known_file.write_text("# Known\n")

        recipes_file = tmp_path / "prompt-recipes.yaml"
        recipes_file.write_text(_make_recipes_yaml([{"name": known_name}]))

        # Adapter has both "known" and an orphaned "orphaned"
        adapter = _make_adapter(
            [
                {"name": "known", "path": known_name},
                {"name": "orphaned", "path": "supervisor/governance/orphaned.md"},
            ]
        )

        issues = validate_governance_material_consistency(
            adapter=adapter, recipes_path=recipes_file, repo_root=tmp_path
        )
        assert len(issues) == 1
        assert issues[0]["type"] == "orphaned_adapter"
        assert "orphaned.md" in issues[0]["message"]

    def test_non_governance_supervisor_not_flagged(self, tmp_path):
        """Adapter supervisor resources outside supervisor/governance/ not flagged."""
        known_name = "supervisor/governance/known.md"
        known_file = tmp_path / known_name
        known_file.parent.mkdir(parents=True, exist_ok=True)
        known_file.write_text("# Known\n")

        recipes_file = tmp_path / "prompt-recipes.yaml"
        recipes_file.write_text(_make_recipes_yaml([{"name": known_name}]))

        # Adapter has apply and manager which are NOT under supervisor/governance/
        adapter = _make_adapter(
            [
                {"name": "known", "path": known_name},
                {"name": "apply", "path": "supervisor/apply.md"},
                {"name": "manager", "path": "supervisor/manager.md"},
            ]
        )

        issues = validate_governance_material_consistency(
            adapter=adapter, recipes_path=recipes_file, repo_root=tmp_path
        )
        assert issues == []

    def test_missing_adapter_default_load_failure(self, tmp_path, monkeypatch):
        """get_adapter returns None -> missing_adapter issue."""
        monkeypatch.setattr(
            "vibe3.adapters.get_adapter",
            lambda name: None,
        )

        issues = validate_governance_material_consistency(repo_root=tmp_path)
        assert len(issues) == 1
        assert issues[0]["type"] == "missing_adapter"
        assert "vibe-center adapter not found" in issues[0]["message"]

    def test_missing_recipe_default_load_failure(self, tmp_path, monkeypatch):
        """PromptManifest.load_default raises -> missing_recipe issue."""
        from vibe3.prompts.manifest import PromptManifest

        monkeypatch.setattr(
            PromptManifest,
            "load_default",
            lambda: None,
        )

        adapter = _make_adapter([])
        issues = validate_governance_material_consistency(
            adapter=adapter, repo_root=tmp_path
        )
        assert len(issues) == 1
        assert issues[0]["type"] == "missing_recipe"
