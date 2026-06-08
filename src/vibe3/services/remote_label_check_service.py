"""Remote label consistency check service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loguru import logger

from vibe3.services.label_consistency_rules import (
    apply_rule_1,
    apply_rule_2,
    apply_rule_3,
    apply_rule_4,
)

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
            rule_names: list[str] = []

            # Track state for Rule 3 guard
            rule1_fired = False
            rule2_kept_state: str | None = None

            # Rule 1: Roadmap label conflict
            roadmap_result = apply_rule_1(issue_number, labels)
            if roadmap_result:
                labels_removed.extend(roadmap_result[0])
                rule_names.append(roadmap_result[1])
                rule1_fired = True

            # Rule 2: Multiple state labels (only if rule 1 didn't apply)
            if not rule1_fired:
                multi_state_result = apply_rule_2(issue_number, labels)
                if multi_state_result:
                    labels_removed.extend(multi_state_result[0])
                    rule_names.append(multi_state_result[1])
                    # Track which state label was kept
                    state_labels = [
                        label for label in labels if label.startswith("state/")
                    ]
                    kept = [
                        label
                        for label in state_labels
                        if label not in multi_state_result[0]
                    ]
                    if kept:
                        rule2_kept_state = kept[0]

            # Rule 3: Orphan execution state labels (only for manager-assigned)
            # GUARD: Skip Rule 3 if:
            # - Rule 1 fired (roadmap issues shouldn't get state labels)
            # - Rule 2 kept a non-execution state label (blocked/done)
            if issue_number in managed_issue_numbers and not rule1_fired:
                # Check if Rule 2 kept a non-execution state
                skip_rule3 = False
                if rule2_kept_state:
                    kept_state_name = rule2_kept_state.replace("state/", "")
                    if kept_state_name not in [
                        "merge-ready",
                        "review",
                        "in-progress",
                        "handoff",
                        "claimed",
                    ]:
                        skip_rule3 = True

                if not skip_rule3:
                    orphan_result = apply_rule_3(
                        issue_number, labels, local_flow_branches
                    )
                    if orphan_result:
                        labels_removed.extend(orphan_result[0])
                        labels_added.extend(orphan_result[1])
                        rule_names.append(orphan_result[2])

            # Rule 4: Orphan orchestra-governed (only for manager-assigned)
            if issue_number in managed_issue_numbers:
                orchestra_result = apply_rule_4(issue_number, labels)
                if orchestra_result:
                    labels_removed.extend(orchestra_result[0])
                    rule_names.append(orchestra_result[1])

            # Deduplicate labels
            labels_removed = list(dict.fromkeys(labels_removed))
            labels_added = list(dict.fromkeys(labels_added))

            # Record result if any changes needed
            if labels_removed or labels_added:
                results.append(
                    RemoteLabelIssue(
                        issue_number=issue_number,
                        labels_removed=labels_removed,
                        labels_added=labels_added,
                        rule=", ".join(rule_names),  # Join all matching rules
                    )
                )

                # Apply changes if not dry run
                if not dry_run:
                    self._apply_label_changes(
                        issue_number, labels_removed, labels_added
                    )

        return results

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
