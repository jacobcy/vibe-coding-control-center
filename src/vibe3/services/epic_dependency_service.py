"""Epic dependency status service for roadmap management."""

import re
from typing import cast

from ..clients.github_client import GitHubClient


def _parse_dependencies_from_body(body: str) -> list[int]:
    """Extract dependency issue numbers from ## Dependencies section.

    Parses the format:
        ## Dependencies
        - Blocked by #N (description)
        - Blocked by #M (another description)

    Args:
        body: Issue body text

    Returns:
        List of dependency issue numbers (order preserved)
    """
    if not body:
        return []

    # Find the ## Dependencies section
    lines = body.split("\n")
    in_deps_section = False
    dependencies: list[int] = []
    seen: set[int] = set()

    for line in lines:
        stripped = line.strip()

        # Check for section header
        if stripped.startswith("## Dependencies"):
            in_deps_section = True
            continue

        # Check for next section (end of dependencies)
        if in_deps_section and stripped.startswith("##"):
            break

        # Parse dependency lines
        if in_deps_section and stripped.startswith("-"):
            # Extract issue numbers from the line
            # Format: "- Blocked by #N (description)" or "- Blocked by #N"
            matches = re.findall(r"#(\d+)", stripped)
            for match in matches:
                num = int(match)
                if num not in seen:
                    seen.add(num)
                    dependencies.append(num)

    return dependencies


class EpicDependencyService:
    """Service for checking epic dependency completion status."""

    def __init__(self, github: GitHubClient):
        """Initialize epic dependency service.

        Args:
            github: GitHub client for issue queries
        """
        self.github = github

    def check_epic_dependency_status(self, issue_number: int) -> dict[str, object]:
        """Check dependency completion status for an epic issue.

        Args:
            issue_number: Epic issue number

        Returns:
            Dict with keys:
                - total: total number of dependencies
                - completed: number of completed dependencies
                - items: list of dependency status dicts
                - is_ready: whether all dependencies are complete
                - summary_text: human-readable summary
        """
        body = self.github.get_issue_body(issue_number)
        if not body:
            return {
                "total": 0,
                "completed": 0,
                "items": [],
                "is_ready": False,
                "summary_text": "No dependencies",
            }

        dep_numbers = _parse_dependencies_from_body(body)
        if not dep_numbers:
            return {
                "total": 0,
                "completed": 0,
                "items": [],
                "is_ready": False,
                "summary_text": "No dependencies",
            }

        # Check each dependency's state
        items: list[dict[str, object]] = []
        completed = 0

        for dep_num in dep_numbers:
            dep_data = self.github.view_issue(dep_num)

            if dep_data is None or dep_data == "network_error":
                # Skip deleted/inaccessible dependencies
                items.append(
                    {
                        "number": dep_num,
                        "state": "DELETED",
                        "completed": False,
                    }
                )
                continue

            if isinstance(dep_data, dict):
                state = dep_data.get("state", "OPEN")
                is_closed = state == "CLOSED"
                items.append(
                    {
                        "number": dep_num,
                        "state": state,
                        "completed": is_closed,
                    }
                )
                if is_closed:
                    completed += 1

        total = len(dep_numbers)
        is_ready = completed == total and total > 0

        # Build summary text
        if is_ready:
            summary_text = f"✓ {completed}/{total} 完成"
        else:
            summary_text = f"⏳ {completed}/{total} 完成"

        return {
            "total": total,
            "completed": completed,
            "items": items,
            "is_ready": is_ready,
            "summary_text": summary_text,
        }

    def enrich_epic_items(
        self, epic_items: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        """Enrich epic items with dependency completion status.

        Args:
            epic_items: List of epic item dicts from fetch_orchestrated_issues

        Returns:
            Same list with each item having a 'dep_status' key added
        """
        enriched: list[dict[str, object]] = []
        for item in epic_items:
            number = cast(int, item["number"])
            dep_status = self.check_epic_dependency_status(number)
            enriched.append({**item, "dep_status": dep_status})
        return enriched
