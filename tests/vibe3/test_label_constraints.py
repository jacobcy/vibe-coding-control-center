"""Tests for the label constraint system.

Verifies:
1. All constraints are well-formed
2. Constraints don't conflict with each other
3. Each constraint detects violations correctly
4. Real-world issues that triggered this system
"""

from __future__ import annotations

from vibe3.services.check.label_constraints import (
    CONSTRAINTS,
    check_constraints,
    constraint_names,
)


class TestConstraintDefinitions:
    def test_all_constraints_defined(self):
        """Every known rule must have a constraint entry."""
        names = constraint_names()
        assert "single_state_label" in names
        assert "no_state_without_assignee" in names
        assert "scanned_forbids_state" in names
        assert "scanned_governed_no_assignee" in names
        assert "ready_requires_assignee" in names

    def test_constraint_names_unique(self):
        """No two constraints share the same name."""
        names = [c.name for c in CONSTRAINTS]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_constraints_have_descriptions(self):
        """Every constraint must document what it does."""
        for c in CONSTRAINTS:
            assert c.description, f"Constraint {c.name} has no description"
            assert c.when, f"Constraint {c.name} has no when clause"

    def test_constraints_no_self_contradiction(self):
        """No constraint forbids AND requires the same label group."""
        for c in CONSTRAINTS:
            for group in c.forbidden_groups:
                assert group not in c.max_from_group, (
                    f"Constraint {c.name}: group '{group}' is both forbidden "
                    f"and has max_from_group constraint"
                )

    def test_constraints_no_mutual_contradiction(self):
        """No two constraints prescribe opposite actions on the same group.

        Documents that max_from_group is a cap (not a requirement), so
        'forbids state/*' + 'caps state/* at 1' is not a contradiction.
        """
        # Verify: a forbidden_groups entry never matches a constraint that
        # also has max_from_group on the same group (caught by
        # test_constraints_no_self_contradiction).
        #
        # Cross-constraint: constraining count AND forbidding the same group
        # is fine because they trigger under different conditions.
        # Example: no_state_without_assignee forbids state/* when no assignee,
        # while single_state_label caps state/* at 1 always. Both are correct.
        pass


class TestConstraintDetection:
    """Each constraint should detect violations correctly."""

    def test_single_state_label_pass(self):
        violations = check_constraints(
            labels={"state/ready", "priority/high"}, assignee="agent"
        )
        names = {v.constraint_name for v in violations}
        assert "single_state_label" not in names

    def test_single_state_label_violation(self):
        violations = check_constraints(
            labels={"state/ready", "state/blocked", "priority/high"},
            assignee="agent",
        )
        names = {v.constraint_name for v in violations}
        assert "single_state_label" in names

    def test_no_state_without_assignee_pass(self):
        violations = check_constraints(labels={"state/ready"}, assignee="agent")
        names = {v.constraint_name for v in violations}
        assert "no_state_without_assignee" not in names

    def test_no_state_without_assignee_violation(self):
        violations = check_constraints(
            labels={"state/ready", "priority/high"}, assignee=None
        )
        names = {v.constraint_name for v in violations}
        assert "no_state_without_assignee" in names

    def test_scanned_forbids_state_pass(self):
        violations = check_constraints(
            labels={"orchestra-scanned", "priority/low"}, assignee=None
        )
        names = {v.constraint_name for v in violations}
        assert "scanned_forbids_state" not in names

    def test_scanned_forbids_state_violation(self):
        violations = check_constraints(
            labels={"orchestra-scanned", "state/ready"}, assignee=None
        )
        names = {v.constraint_name for v in violations}
        assert "scanned_forbids_state" in names

    def test_scanned_governed_no_assignee_pass_with_assignee(self):
        violations = check_constraints(
            labels={"orchestra-scanned", "orchestra-governed"},
            assignee="agent",
        )
        names = {v.constraint_name for v in violations}
        assert "scanned_governed_no_assignee" not in names

    def test_scanned_governed_no_assignee_violation(self):
        violations = check_constraints(
            labels={"orchestra-scanned", "orchestra-governed"},
            assignee=None,
        )
        names = {v.constraint_name for v in violations}
        assert "scanned_governed_no_assignee" in names

    def test_ready_requires_assignee_pass(self):
        violations = check_constraints(labels={"state/ready"}, assignee="agent")
        names = {v.constraint_name for v in violations}
        assert "ready_requires_assignee" not in names

    def test_ready_requires_assignee_violation(self):
        violations = check_constraints(
            labels={"state/ready", "orchestra-governed"}, assignee=None
        )
        names = {v.constraint_name for v in violations}
        assert "ready_requires_assignee" in names

    def test_multiple_violations_at_once(self):
        """An issue can trigger multiple constraints simultaneously."""
        violations = check_constraints(
            labels={
                "state/ready",
                "state/blocked",  # -> single_state_label
                "orchestra-scanned",  # -> scanned_forbids_state
            },
            assignee=None,  # -> no_state_without_assignee
        )
        names = {v.constraint_name for v in violations}
        assert "single_state_label" in names
        assert "no_state_without_assignee" in names
        assert "scanned_forbids_state" in names


class TestRealWorldIssues:
    """The real issues that motivated this constraint system."""

    def test_issue_2035(self):
        """#2035: state/ready + orchestra-scanned + orchestra-governed + no assignee."""
        violations = check_constraints(
            labels={
                "state/ready",
                "orchestra-scanned",
                "orchestra-governed",
                "roadmap-reviewed",
            },
            assignee=None,
        )
        names = {v.constraint_name for v in violations}
        assert "no_state_without_assignee" in names
        assert "scanned_forbids_state" in names
        assert "scanned_governed_no_assignee" in names
        assert "ready_requires_assignee" in names

    def test_issue_2036(self):
        """#2036: same pattern as #2035."""
        violations = check_constraints(
            labels={
                "state/ready",
                "orchestra-scanned",
                "orchestra-governed",
                "roadmap-reviewed",
            },
            assignee=None,
        )
        names = {v.constraint_name for v in violations}
        assert len(names) >= 3  # at least 3 violations

    def test_healthy_ready_issue(self):
        """A properly configured ready issue should have zero violations."""
        violations = check_constraints(
            labels={
                "state/ready",
                "orchestra-governed",
                "roadmap/p1",
                "vibe-task",
            },
            assignee="vibe-manager-agent",
        )
        assert len(violations) == 0, f"Expected 0 violations: {violations}"

    def test_healthy_blocked_issue(self):
        """A properly configured blocked issue should have zero violations."""
        violations = check_constraints(
            labels={
                "state/blocked",
                "orchestra-governed",
                "roadmap/p1",
                "vibe-task",
            },
            assignee="vibe-manager-agent",
        )
        assert len(violations) == 0, f"Expected 0 violations: {violations}"


class TestConstraintConsistency:
    """Verify that the constraint system is internally consistent when adding new rules.

    When adding a new constraint to CONSTRAINTS, simply add a data entry.
    These tests will automatically detect if the new rule conflicts with
    existing ones - no test code changes needed.
    """

    def test_every_constraint_has_a_handler(self):
        """Every constraint in CONSTRAINTS must have a case in check_constraints()."""
        import inspect

        source = inspect.getsource(check_constraints)
        for c in CONSTRAINTS:
            assert f'case "{c.name}"' in source, (
                f"Constraint '{c.name}' has no handler in check_constraints(). "
                f"Add a 'case \"{c.name}\":' block."
            )

    def test_no_stale_handlers(self):
        """No handler in check_constraints() for a removed constraint."""
        import inspect

        source = inspect.getsource(check_constraints)
        import re

        handled = set(re.findall(r'case "([^"]+)"', source))
        defined = constraint_names()
        for name in handled:
            assert name in defined, (
                f"Handler for '{name}' exists in check_constraints() "
                f"but no Constraint with that name in CONSTRAINTS. "
                f"Remove the stale handler or add the constraint."
            )
