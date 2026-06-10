"""Unit tests for material_loader factory."""

from pathlib import Path

from vibe3.services.shared.file_loader import material_loader


class TestMaterialLoader:
    """Tests for material file loading."""

    def test_load_all_reads_markdown_files(self, tmp_path: Path) -> None:
        """Test that load_all reads .md files and returns entries."""
        (tmp_path / "file1.md").write_text("# File 1\nContent 1")
        (tmp_path / "file2.md").write_text("# File 2\nContent 2")

        loader = material_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 2
        assert entries[0].name == "file1.md"
        assert entries[1].name == "file2.md"
        assert entries[0].content == "# File 1\nContent 1"
        assert entries[1].content == "# File 2\nContent 2"
        assert len(entries[0].content_hash) == 16
        assert len(entries[1].content_hash) == 16
        assert entries[0].mtime > 0
        assert entries[1].mtime > 0

    def test_load_all_returns_empty_for_missing_directory(self, tmp_path: Path) -> None:
        """Test that load_all returns empty tuple for missing directory."""
        missing_dir = tmp_path / "nonexistent"
        loader = material_loader(missing_dir)
        entries = loader.load_all()

        assert entries == ()

    def test_load_all_returns_empty_for_empty_directory(self, tmp_path: Path) -> None:
        """Test that load_all returns empty tuple for empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        loader = material_loader(empty_dir)
        entries = loader.load_all()

        assert entries == ()

    def test_load_all_ignores_non_markdown_files(self, tmp_path: Path) -> None:
        """Test that load_all only reads .md files."""
        (tmp_path / "material.md").write_text("# Material")
        (tmp_path / "config.yaml").write_text("key: value")
        (tmp_path / "data.txt").write_text("text data")

        loader = material_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 1
        assert entries[0].name == "material.md"

    def test_load_single_material(self, tmp_path: Path) -> None:
        """Test loading a single material by name."""
        (tmp_path / "assignee-pool.md").write_text("# Assignee Pool")

        loader = material_loader(tmp_path)
        entry = loader.load("assignee-pool.md")

        assert entry is not None
        assert entry.name == "assignee-pool.md"
        assert entry.content == "# Assignee Pool"

    def test_load_single_nonexistent_returns_none(self, tmp_path: Path) -> None:
        """Test that loading a nonexistent file returns None."""
        loader = material_loader(tmp_path)
        entry = loader.load("nonexistent.md")

        assert entry is None

    def test_content_hash_is_stable(self, tmp_path: Path) -> None:
        """Test that the same content produces the same hash."""
        (tmp_path / "file.md").write_text("Stable content")

        loader1 = material_loader(tmp_path)
        loader2 = material_loader(tmp_path)
        entry1 = loader1.load("file.md")
        entry2 = loader2.load("file.md")

        assert entry1 is not None
        assert entry2 is not None
        assert entry1.content_hash == entry2.content_hash

    def test_content_hash_differs_for_different_content(self, tmp_path: Path) -> None:
        """Test that different content produces different hashes."""
        (tmp_path / "file1.md").write_text("Content A")
        (tmp_path / "file2.md").write_text("Content B")

        loader = material_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 2
        assert entries[0].content_hash != entries[1].content_hash

    def test_entries_sorted_by_name(self, tmp_path: Path) -> None:
        """Test that entries are sorted by filename."""
        (tmp_path / "zeta.md").write_text("Z")
        (tmp_path / "alpha.md").write_text("A")
        (tmp_path / "beta.md").write_text("B")

        loader = material_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 3
        assert entries[0].name == "alpha.md"
        assert entries[1].name == "beta.md"
        assert entries[2].name == "zeta.md"

    def test_load_all_handles_read_errors_gracefully(self, tmp_path: Path) -> None:
        """Test that load_all handles read errors gracefully."""
        (tmp_path / "valid.md").write_text("Valid content")
        bad_path = tmp_path / "bad.md"
        bad_path.mkdir()

        loader = material_loader(tmp_path)
        entries = loader.load_all()

        assert len(entries) == 1
        assert entries[0].name == "valid.md"

    def test_path_is_absolute(self, tmp_path: Path) -> None:
        """Test that returned path is absolute."""
        (tmp_path / "file.md").write_text("Content")

        loader = material_loader(tmp_path)
        entry = loader.load("file.md")

        assert entry is not None
        assert entry.path.is_absolute()
        assert entry.path.name == "file.md"

    def test_content_preserves_newlines(self, tmp_path: Path) -> None:
        """Test that content preserves newlines and formatting."""
        content = "# Title\n\nParagraph 1\n\nParagraph 2\n"
        (tmp_path / "formatted.md").write_text(content)

        loader = material_loader(tmp_path)
        entry = loader.load("formatted.md")

        assert entry is not None
        assert entry.content == content
