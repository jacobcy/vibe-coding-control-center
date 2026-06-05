"""Manager scope guard policy tests."""

from pathlib import Path


def test_audit_branch_validation_uses_merge_base_diff() -> None:
    policy = Path("supervisor/policies/run.md").read_text()

    assert "git diff --name-only origin/main...HEAD" in policy
    assert "git diff --name-only origin/main..HEAD" not in policy
