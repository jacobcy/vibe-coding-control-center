"""Data-driven label constraint system.

Each constraint is a self-contained rule expressed as data.
The check_constraints() function validates an issue's labels against all constraints.
The test verifies that no two constraints prescribe contradictory actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LabelConstraint:
    """A single label consistency rule.

    Attributes:
        name: Unique constraint identifier.
        description: Human-readable description.
        when: Python expression string describing the trigger condition.
        forbidden_groups: Label groups where NO label from the group may be present
            when this constraint triggers. Supports glob-style group names
            ending in '/*' (e.g., 'state/*' matches any state/ label).
        max_from_group: Maximum allowed labels from a group when triggered.
        action: What to do when constraint is violated (for documentation).
    """

    name: str
    description: str
    when: str
    forbidden_groups: frozenset[str] = frozenset()
    max_from_group: dict[str, int] = field(default_factory=dict)
    action: str = ""


# -- Constraint definitions ------------------------------------------------

CONSTRAINTS: tuple[LabelConstraint, ...] = (
    LabelConstraint(
        name="single_state_label",
        description="At most one state/* label per issue",
        when="always",
        max_from_group={"state/*": 1},
        action="remove all state/* except the highest-priority one",
    ),
    LabelConstraint(
        name="no_state_without_assignee",
        description="No state/* label when issue has no assignee",
        when="issue has no assignee",
        forbidden_groups=frozenset({"state/*"}),
        action="remove all state/* labels, reset for governance re-evaluation",
    ),
    LabelConstraint(
        name="scanned_forbids_state",
        description="orchestra-scanned must not coexist with any state/* label",
        when="issue has orchestra-scanned label",
        forbidden_groups=frozenset({"state/*"}),
        action="remove all state/* and orchestra-scanned labels",
    ),
    LabelConstraint(
        name="scanned_governed_no_assignee",
        description="orchestra-scanned + orchestra-governed without assignee: "
        "both governance labels should be removed for re-evaluation",
        when="issue has orchestra-scanned AND orchestra-governed AND no assignee",
        forbidden_groups=frozenset({"orchestra-scanned", "orchestra-governed"}),
        action="remove orchestra-scanned and orchestra-governed",
    ),
    LabelConstraint(
        name="ready_requires_assignee",
        description="state/ready requires an assignee",
        when="issue has state/ready",
        forbidden_groups=frozenset({"state/ready"}),
        action="remove state/ready if no assignee",
    ),
)


def _matches_group(label: str, group: str) -> bool:
    """Check if a label matches a group pattern.

    Groups ending in '/*' match any label with that prefix.
    Otherwise, exact match is required.
    """
    if group.endswith("/*"):
        prefix = group[:-2]  # remove /*
        return label.startswith(prefix + "/") or label == prefix
    return label == group


def _labels_in_group(labels: set[str], group: str) -> set[str]:
    """Return labels that belong to the given group."""
    return {lb for lb in labels if _matches_group(lb, group)}


@dataclass(frozen=True)
class ConstraintViolation:
    constraint_name: str
    description: str
    detail: str
    action: str


def check_constraints(
    *,
    labels: set[str],
    assignee: str | None = None,
) -> list[ConstraintViolation]:
    """Validate labels against all constraints.

    Args:
        labels: Set of label names on the issue.
        assignee: Issue assignee login, or None.

    Returns:
        List of violations. Empty list means all constraints pass.
    """
    violations: list[ConstraintViolation] = []

    for c in CONSTRAINTS:
        match c.name:
            case "single_state_label":
                max_n = c.max_from_group.get("state/*", 1)
                state_labels = _labels_in_group(labels, "state/*")
                if len(state_labels) > max_n:
                    violations.append(
                        ConstraintViolation(
                            constraint_name=c.name,
                            description=c.description,
                            detail=f"Found {len(state_labels)} state labels: "
                            f"{sorted(state_labels)}",
                            action=c.action,
                        )
                    )

            case "no_state_without_assignee":
                if assignee is None or assignee == "":
                    state_labels = _labels_in_group(labels, "state/*")
                    if state_labels:
                        violations.append(
                            ConstraintViolation(
                                constraint_name=c.name,
                                description=c.description,
                                detail=f"No assignee but has state labels: "
                                f"{sorted(state_labels)}",
                                action=c.action,
                            )
                        )

            case "scanned_forbids_state":
                if "orchestra-scanned" in labels:
                    state_labels = _labels_in_group(labels, "state/*")
                    if state_labels:
                        violations.append(
                            ConstraintViolation(
                                constraint_name=c.name,
                                description=c.description,
                                detail=f"orchestra-scanned coexists with: "
                                f"{sorted(state_labels)}",
                                action=c.action,
                            )
                        )

            case "scanned_governed_no_assignee":
                has_scanned = "orchestra-scanned" in labels
                has_governed = "orchestra-governed" in labels
                no_assignee = not assignee
                if has_scanned and has_governed and no_assignee:
                    violations.append(
                        ConstraintViolation(
                            constraint_name=c.name,
                            description=c.description,
                            detail="Both governance labels present without assignee",
                            action=c.action,
                        )
                    )

            case "ready_requires_assignee":
                if "state/ready" in labels and (not assignee):
                    violations.append(
                        ConstraintViolation(
                            constraint_name=c.name,
                            description=c.description,
                            detail="state/ready without assignee",
                            action=c.action,
                        )
                    )

    return violations


def constraint_names() -> set[str]:
    """Return all constraint names for test verification."""
    return {c.name for c in CONSTRAINTS}
