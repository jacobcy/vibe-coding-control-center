"""Unit tests for policy_loader factory."""

from pathlib import Path

import pytest
import yaml

from vibe3.services.file_loader import policy_loader, resolve_manager_usernames


class TestPolicyLoader:
    """Tests for policy file loading."""

    def test_load_all_reads_yaml_files(self, tmp_path: Path) -> None:
        """Test that load_all reads .yaml files and returns entries."""
        policy1_data = {"name": "policy1", "value": 100}
        policy2_data = {"name": "policy2", "enabled": True}

        (tmp_path / "policy1.yaml").write_text(yaml.dump(policy1_data))
        (tmp_path / "policy2.yaml").write_text(yaml.dump(policy2_data))

        loader = policy_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 2
        assert entries[0].name == "policy1.yaml"
        assert entries[1].name == "policy2.yaml"
        assert entries[0].data == policy1_data
        assert entries[1].data == policy2_data
        assert len(entries[0].content_hash) == 16
        assert len(entries[1].content_hash) == 16
        assert entries[0].mtime > 0
        assert entries[1].mtime > 0

    def test_load_all_returns_empty_for_missing_directory(self, tmp_path: Path) -> None:
        """Test that load_all returns empty tuple for missing directory."""
        missing_dir = tmp_path / "nonexistent"
        loader = policy_loader(missing_dir)
        entries = loader.load_all()

        assert entries == ()

    def test_load_all_skips_invalid_yaml(self, tmp_path: Path) -> None:
        """Test that load_all skips files with invalid YAML."""
        valid_data = {"key": "value"}
        (tmp_path / "valid.yaml").write_text(yaml.dump(valid_data))
        (tmp_path / "invalid.yaml").write_text("invalid: yaml: content: [unclosed")

        loader = policy_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 1
        assert entries[0].name == "valid.yaml"
        assert entries[0].data == valid_data

    def test_load_all_accepts_yml_extension(self, tmp_path: Path) -> None:
        """Test that load_all accepts both .yaml and .yml files."""
        data = {"key": "value"}
        (tmp_path / "policy.yaml").write_text(yaml.dump(data))
        (tmp_path / "config.yml").write_text(yaml.dump(data))

        loader = policy_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 2
        assert entries[0].name == "config.yml"
        assert entries[1].name == "policy.yaml"

    def test_load_single_policy(self, tmp_path: Path) -> None:
        """Test loading a single policy by name."""
        data = {"name": "autoharness", "version": "1.0"}
        (tmp_path / "autoharness.yaml").write_text(yaml.dump(data))

        loader = policy_loader(tmp_path)
        entry = loader.load("autoharness.yaml")

        assert entry is not None
        assert entry.name == "autoharness.yaml"
        assert entry.data == data

    def test_load_single_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Test that loading a nonexistent file returns None."""
        loader = policy_loader(tmp_path)
        entry = loader.load("nonexistent.yaml")

        assert entry is None

    def test_content_hash_stable(self, tmp_path: Path) -> None:
        """Test that the same content produces the same hash."""
        data = {"key": "value"}
        content = yaml.dump(data)
        (tmp_path / "policy.yaml").write_text(content)

        loader1 = policy_loader(tmp_path)
        loader2 = policy_loader(tmp_path)
        entry1 = loader1.load("policy.yaml")
        entry2 = loader2.load("policy.yaml")

        assert entry1 is not None
        assert entry2 is not None
        assert entry1.content_hash == entry2.content_hash

    def test_content_hash_differs_for_different_content(self, tmp_path: Path) -> None:
        """Test that different content produces different hashes."""
        (tmp_path / "policy1.yaml").write_text(yaml.dump({"a": 1}))
        (tmp_path / "policy2.yaml").write_text(yaml.dump({"b": 2}))

        loader = policy_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 2
        assert entries[0].content_hash != entries[1].content_hash

    def test_entries_sorted_by_name(self, tmp_path: Path) -> None:
        """Test that entries are sorted by filename."""
        (tmp_path / "zeta.yaml").write_text(yaml.dump({"z": 1}))
        (tmp_path / "alpha.yaml").write_text(yaml.dump({"a": 1}))
        (tmp_path / "beta.yaml").write_text(yaml.dump({"b": 1}))

        loader = policy_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 3
        assert entries[0].name == "alpha.yaml"
        assert entries[1].name == "beta.yaml"
        assert entries[2].name == "zeta.yaml"

    def test_load_skips_non_dict_yaml(self, tmp_path: Path) -> None:
        """Test that load skips YAML files that don't contain dicts."""
        (tmp_path / "list.yaml").write_text(yaml.dump(["item1", "item2"]))
        (tmp_path / "valid.yaml").write_text(yaml.dump({"key": "value"}))

        loader = policy_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 1
        assert entries[0].name == "valid.yaml"

    def test_path_is_absolute(self, tmp_path: Path) -> None:
        """Test that returned path is absolute."""
        (tmp_path / "policy.yaml").write_text(yaml.dump({"k": "v"}))

        loader = policy_loader(tmp_path)
        entry = loader.load("policy.yaml")

        assert entry is not None
        assert entry.path.is_absolute()
        assert entry.path.name == "policy.yaml"


class TestResolveManagerUsernames:
    """Tests for resolve_manager_usernames function."""

    def test_resolve_manager_usernames_returns_tuple(self) -> None:
        """Test that resolve_manager_usernames returns a tuple."""
        usernames = resolve_manager_usernames()

        assert isinstance(usernames, tuple)
        assert len(usernames) > 0
        assert all(isinstance(u, str) for u in usernames)

    def test_resolve_manager_usernames_uses_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that resolve_manager_usernames uses config."""
        from vibe3.models import OrchestraConfig

        mock_orchestra_config = OrchestraConfig(
            manager_usernames=("test-manager-1", "test-manager-2")
        )
        mock_config = type("MockConfig", (), {"orchestra": mock_orchestra_config})()

        monkeypatch.setattr(
            "vibe3.config.get_config_with_env_override",
            lambda: mock_config,
        )

        usernames = resolve_manager_usernames()

        assert usernames == ("test-manager-1", "test-manager-2")
