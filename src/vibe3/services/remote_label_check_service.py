"""Remote label consistency check service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from vibe3.clients import GhIssueLabelPort, GitHubClient, SQLiteClient


@dataclass
class RemoteLabelIssue:
    """Result for a single issue with label changes."""

    issue_number: int
    labels_removed: list[str] = field(default_factory=list)
    labels_added: list[str] = field(default_factory=list)
    rule: str = ""  # rule name for grouping


@dataclass
class RemoteLabelCheckResult:
    """Aggregate result for remote label check."""

    total_issues: int
    issues_found: int
    results: list[RemoteLabelIssue] = field(default_factory=list)
    total_removed: int = 0
    total_added: int = 0


class RemoteLabelCheckService:
    """Service for checking remote GitHub issue label consistency.

    Implements 4 rules for label consistency:
    1. Roadmap label conflict: roadmap/rfc or roadmap/epic should not
       have state/* labels
    2. Multiple state labels: Keep highest priority state, remove others
    3. Orphan execution state labels: Manager-assigned issues with
       execution state but no local flow record
    4. Orphan orchestra-governed: Manager-assigned issues with
       orchestra-governed but no state/* or roadmap labels
    """

    # State label priority (highest to lowest)
    # Note: This order differs from check_service.py intentionally
    # merge-ready is closer to done than review/in-progress
    STATE_PRIORITY = [
        "blocked",
        "done",
        "merge-ready",
        "review",
        "in-progress",
        "handoff",
        "claimed",
        "ready",
    ]

    # Execution state labels (for rule 3)
    EXECUTION_STATE_LABELS = {
        "state/merge-ready",
        "state/review",
        "state/in-progress",
        "state/handoff",
        "state/claimed",
    }

    def __init__(
        self,
        *,
        github_client: GitHubClient,
        store: SQLiteClient,
        label_port: GhIssueLabelPort,
        manager_usernames: tuple[str, ...],
    ) -> None:
        """Initialize the service with dependencies.

        Args:
            github_client: For fetching remote issues
            store: For checking local flow records
            label_port: For label CRUD operations
            manager_usernames: Tuple of manager usernames for rules 3/4
        """
        self.github_client = github_client
        self.store = store
        self.label_port = label_port
        self.manager_usernames = manager_usernames

    def check(self, *, dry_run: bool = False) -> RemoteLabelCheckResult:
        """Execute all 4 label consistency rules.

        Args:
            dry_run: If True, only report changes without applying them

        Returns:
            RemoteLabelCheckResult with all issues found and changes made
        """
        # Step 1: Fetch all open issues
        all_issues = self._fetch_all_issues()
        total_issues = len(all_issues)

        if total_issues == 0:
            logger.info("No open issues found")
            return RemoteLabelCheckResult(
                total_issues=0,
                issues_found=0,
            )

        # Step 2: Identify manager-assigned issues (for rules 3/4)
        managed_issue_numbers = self._get_managed_issue_numbers(all_issues)

        # Step 3: Get local flow branches (for rule 3)
        local_flow_branches = self._get_local_flow_branches()

        # Step 4: Execute all 4 rules
        results = self._run_rules(
            all_issues=all_issues,
            managed_issue_numbers=managed_issue_numbers,
            local_flow_branches=local_flow_branches,
            dry_run=dry_run,
        )

        # Calculate totals
        issues_found = len(results)
        total_removed = sum(len(r.labels_removed) for r in results)
        total_added = sum(len(r.labels_added) for r in results)

        return RemoteLabelCheckResult(
            total_issues=total_issues,
            issues_found=issues_found,
            results=results,
            total_removed=total_removed,
            total_added=total_added,
        )

    def _fetch_all_issues(self) -> list[dict]:
        """Fetch all open issues from GitHub.

        Returns:
            List of issue payloads with number, title, labels, assignees
        """
        logger.info("Fetching all open issues from GitHub...")
        issues = self.github_client.list_issues(
            limit=5000,
            state="open",
            fields=["number", "title", "labels", "assignees"],
        )
        logger.info(f"Fetched {len(issues)} open issues")
        return issues

    def _get_managed_issue_numbers(self, all_issues: list[dict]) -> set[int]:
        """Identify issues assigned to manager usernames.

        Args:
            all_issues: List of issue payloads

        Returns:
            Set of issue numbers assigned to managers
        """
        if not self.manager_usernames:
            logger.info("No manager usernames configured, skipping manager-only rules")
            return set()

        managed = set()
        for issue in all_issues:
            issue_number = issue.get("number")
            if not isinstance(issue_number, int):
                continue

            assignees = issue.get("assignees", [])

            # Check if any assignee is a manager
            for assignee in assignees:
                login = assignee.get("login", "")
                if login in self.manager_usernames:
                    managed.add(issue_number)
                    break

        logger.info(f"Found {len(managed)} issues assigned to managers")
        return managed

    def _get_local_flow_branches(self) -> set[str]:
        """Get set of branches that have local flow records.

        Returns:
            Set of branch names with flow records
        """
        logger.info("Fetching local flow records...")
        flows = self.store.get_all_flows()
        branches = {flow.get("branch", "") for flow in flows if flow.get("branch")}
        logger.info(f"Found {len(branches)} branches with local flow records")
        return branches

    def _run_rules(
        self,
        *,
        all_issues: list[dict],
        managed_issue_numbers: set[int],
        local_flow_branches: set[str],
        dry_run: bool,
    ) -> list[RemoteLabelIssue]:
        """Execute all 4 rules in order.

        Args:
            all_issues: All open issues
            managed_issue_numbers: Issue numbers assigned to managers
            local_flow_branches: Branches with local flow records
            dry_run: If True, only report changes

        Returns:
            List of RemoteLabelIssue results
        """
        results: list[RemoteLabelIssue] = []

        for issue in all_issues:
            issue_number = issue.get("number")
            if not isinstance(issue_number, int):
                continue

            labels = [label.get("name", "") for label in issue.get("labels", [])]

            # Collect changes from all rules
            labels_removed: list[str] = []
            labels_added: list[str] = []
            rule_name = ""

            # Rule 1: Roadmap label conflict
            roadmap_result = self._apply_rule_1(issue_number, labels)
            if roadmap_result:
                labels_removed.extend(roadmap_result[0])
                rule_name = roadmap_result[1]

            # Rule 2: Multiple state labels (only if rule 1 didn't apply)
            if not rule_name:
                multi_state_result = self._apply_rule_2(issue_number, labels)
                if multi_state_result:
                    labels_removed.extend(multi_state_result[0])
                    rule_name = multi_state_result[1]

            # Rule 3: Orphan execution state labels (only for manager-assigned)
            if issue_number in managed_issue_numbers:
                orphan_result = self._apply_rule_3(
                    issue_number, labels, local_flow_branches
                )
                if orphan_result:
                    labels_removed.extend(orphan_result[0])
                    labels_added.extend(orphan_result[1])
                    rule_name = orphan_result[2]

            # Rule 4: Orphan orchestra-governed (only for manager-assigned)
            if issue_number in managed_issue_numbers:
                orchestra_result = self._apply_rule_4(issue_number, labels)
                if orchestra_result:
                    labels_removed.extend(orchestra_result[0])
                    rule_name = orchestra_result[1]

            # Record result if any changes needed
            if labels_removed or labels_added:
                results.append(
                    RemoteLabelIssue(
                        issue_number=issue_number,
                        labels_removed=labels_removed,
                        labels_added=labels_added,
                        rule=rule_name,
                    )
                )

                # Apply changes if not dry run
                if not dry_run:
                    self._apply_label_changes(
                        issue_number, labels_removed, labels_added
                    )

        return results

    def _apply_rule_1(
        self, issue_number: int, labels: list[str]
    ) -> tuple[list[str], str] | None:
        """Rule 1: Roadmap label conflict.

        If issue has roadmap/rfc or roadmap/epic, all state/* labels should be removed.

        Returns:
            Tuple of (labels_to_remove, rule_name) or None
        """
        has_roadmap_rfc = "roadmap/rfc" in labels
        has_roadmap_epic = "roadmap/epic" in labels

        if not (has_roadmap_rfc or has_roadmap_epic):
            return None

        # Find all state/* labels
        state_labels = [label for label in labels if label.startswith("state/")]

        if not state_labels:
            return None

        logger.bind(
            issue_number=issue_number,
            roadmap="rfc" if has_roadmap_rfc else "epic",
            state_labels=state_labels,
        ).info("Rule 1: Roadmap label conflict detected")

        return (state_labels, "规则 1 (roadmap 标签冲突)")

    def _apply_rule_2(
        self, issue_number: int, labels: list[str]
    ) -> tuple[list[str], str] | None:
        """Rule 2: Multiple state labels.

        Keep highest priority state, remove others.

        Returns:
            Tuple of (labels_to_remove, rule_name) or None
        """
        state_labels = [label for label in labels if label.startswith("state/")]

        if len(state_labels) <= 1:
            return None

        # Find highest priority state
        highest_priority_state = None
        highest_priority_idx = len(self.STATE_PRIORITY)

        for state_label in state_labels:
            # Extract state name (e.g., "state/blocked" -> "blocked")
            state_name = state_label.replace("state/", "")

            if state_name in self.STATE_PRIORITY:
                idx = self.STATE_PRIORITY.index(state_name)
                if idx < highest_priority_idx:
                    highest_priority_idx = idx
                    highest_priority_state = state_label

        if highest_priority_state is None:
            # Unknown state labels, skip auto-fix
            logger.bind(
                issue_number=issue_number,
                state_labels=state_labels,
            ).warning("Rule 2: Unknown state labels, skipping auto-fix")
            return None

        # Remove all state labels except the highest priority one
        labels_to_remove = [
            label for label in state_labels if label != highest_priority_state
        ]

        logger.bind(
            issue_number=issue_number,
            keep=highest_priority_state,
            remove=labels_to_remove,
        ).info("Rule 2: Multiple state labels detected")

        return (labels_to_remove, "规则 2 (多个 state 标签)")

    def _apply_rule_3(
        self,
        issue_number: int,
        labels: list[str],
        local_flow_branches: set[str],
    ) -> tuple[list[str], list[str], str] | None:
        """Rule 3: Orphan execution state labels.

        Manager-assigned issue with execution state but no local flow record.

        Returns:
            Tuple of (labels_to_remove, labels_to_add, rule_name) or None
        """
        # Check if issue has any execution state label
        execution_labels = [
            label for label in labels if label in self.EXECUTION_STATE_LABELS
        ]

        if not execution_labels:
            return None

        # Check if canonical branch has local flow record
        canonical_branch = f"task/issue-{issue_number}"

        if canonical_branch in local_flow_branches:
            return None

        # Issue has execution state but no local flow
        logger.bind(
            issue_number=issue_number,
            execution_labels=execution_labels,
            expected_branch=canonical_branch,
        ).info("Rule 3: Orphan execution state detected")

        return (
            execution_labels,
            ["state/ready"],
            "规则 3 (孤儿执行态标签)",
        )

    def _apply_rule_4(
        self, issue_number: int, labels: list[str]
    ) -> tuple[list[str], str] | None:
        """Rule 4: Orphan orchestra-governed.

        Manager-assigned issue with orchestra-governed but no state/* or roadmap labels.

        Returns:
            Tuple of (labels_to_remove, rule_name) or None
        """
        if "orchestra-governed" not in labels:
            return None

        # Check if issue has any state/* label
        has_state_label = any(label.startswith("state/") for label in labels)

        # Check if issue has roadmap labels
        has_roadmap_label = "roadmap/rfc" in labels or "roadmap/epic" in labels

        if has_state_label or has_roadmap_label:
            return None

        # Issue has orchestra-governed but no state/* or roadmap labels
        logger.bind(
            issue_number=issue_number,
        ).info("Rule 4: Orphan orchestra-governed detected")

        return (["orchestra-governed"], "规则 4 (孤儿 orchestra-governed)")

    def _apply_label_changes(
        self,
        issue_number: int,
        labels_removed: list[str],
        labels_added: list[str],
    ) -> None:
        """Apply label changes to an issue.

        Args:
            issue_number: Issue number
            labels_removed: Labels to remove
            labels_added: Labels to add
        """
        # Remove labels first
        for label in labels_removed:
            success = self.label_port.remove_issue_label(issue_number, label)
            if success:
                logger.bind(
                    issue_number=issue_number,
                    label=label,
                ).info("Removed label from issue")
            else:
                logger.bind(
                    issue_number=issue_number,
                    label=label,
                ).warning("Failed to remove label from issue")

        # Add labels
        for label in labels_added:
            success = self.label_port.add_issue_label(issue_number, label)
            if success:
                logger.bind(
                    issue_number=issue_number,
                    label=label,
                ).info("Added label to issue")
            else:
                logger.bind(
                    issue_number=issue_number,
                    label=label,
                ).warning("Failed to add label to issue")
