"""Tests for vibe3.utils.hash_helpers."""

from types import SimpleNamespace

from vibe3.utils.hash_helpers import compute_governance_hash


class TestComputeGovernanceHash:
    """Direct unit tests for compute_governance_hash."""

    def test_empty_entries_returns_none(self) -> None:
        assert compute_governance_hash([]) is None

    def test_single_entry(self) -> None:
        entry = SimpleNamespace(name="test", content_hash="abc123def456")
        result = compute_governance_hash([entry])  # type: ignore[arg-type]
        assert result is not None
        assert len(result) == 16

    def test_sorted_order_is_deterministic(self) -> None:
        entries_a = [
            SimpleNamespace(name="b", content_hash="hash1"),
            SimpleNamespace(name="a", content_hash="hash2"),
        ]
        entries_b = [
            SimpleNamespace(name="a", content_hash="hash2"),
            SimpleNamespace(name="b", content_hash="hash1"),
        ]
        assert compute_governance_hash(entries_a) == compute_governance_hash(  # type: ignore[arg-type]
            entries_b
        )

    def test_content_change_affects_hash(self) -> None:
        entry_v1 = SimpleNamespace(name="policy", content_hash="aaa")
        entry_v2 = SimpleNamespace(name="policy", content_hash="bbb")
        assert compute_governance_hash([entry_v1]) != compute_governance_hash(  # type: ignore[arg-type]
            [entry_v2]
        )

    def test_name_change_affects_hash(self) -> None:
        entry_a = SimpleNamespace(name="alpha", content_hash="same")
        entry_b = SimpleNamespace(name="beta", content_hash="same")
        assert compute_governance_hash([entry_a]) != compute_governance_hash(  # type: ignore[arg-type]
            [entry_b]
        )

    def test_multiple_entries(self) -> None:
        import hashlib

        entries = [
            SimpleNamespace(name="c", content_hash="h3"),
            SimpleNamespace(name="a", content_hash="h1"),
            SimpleNamespace(name="b", content_hash="h2"),
        ]
        result = compute_governance_hash(entries)  # type: ignore[arg-type]
        assert result is not None
        assert len(result) == 16
        expected_parts = sorted(f"{e.name}|{e.content_hash}" for e in entries)
        expected = hashlib.sha256("|".join(expected_parts).encode()).hexdigest()[:16]
        assert result == expected
