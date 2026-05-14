"""GitHub Projects v2 GraphQL API client."""

import json
import subprocess
from typing import Any, cast

from vibe3.exceptions import GitHubError
from vibe3.models.github_project import Item, ProjectInfo


class GitHubProjectClient:
    """Client for GitHub Projects v2 GraphQL API operations.

    Uses `gh api graphql` as backend. Requires `gh` CLI with `project` scope.
    """

    def __init__(
        self, owner: str, project_number: int, owner_type: str = "user"
    ) -> None:
        """Initialize client with project details.

        Args:
            owner: GitHub user or organization login
            project_number: Project number (from URL)
            owner_type: "user" or "organization"
        """
        self.owner = owner
        self.project_number = project_number
        self.owner_type = owner_type

    def _run_graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict:
        """Execute GraphQL query via `gh api graphql`.

        Args:
            query: GraphQL query string
            variables: Optional dict of variables (values auto-typed by -F)

        Returns:
            The "data" key from GraphQL response

        Raises:
            GitHubError: On subprocess failure, JSON parse error, or GraphQL errors
        """
        cmd = ["gh", "api", "graphql", "-f", f"query={query}"]

        if variables:
            for key, value in variables.items():
                # -F auto-detects type (Int, String, etc.)
                cmd.extend(["-F", f"{key}={value}"])

        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            data = json.loads(result.stdout)

            if "errors" in data:
                error_msg = json.dumps(data["errors"], indent=2)
                raise GitHubError(
                    status_code=1,
                    message=f"GraphQL errors:\n{error_msg}",
                )

            return cast(dict, data["data"])

        except subprocess.CalledProcessError as e:
            error_msg = (e.stderr or str(e)).strip()
            raise GitHubError(
                status_code=e.returncode,
                message=f"gh api graphql failed: {error_msg}",
            ) from e
        except json.JSONDecodeError as e:
            raise GitHubError(
                status_code=1,
                message=f"Failed to parse JSON response: {e.msg}",
            ) from e

    def get_project_info(
        self, owner: str | None = None, project_number: int | None = None
    ) -> ProjectInfo:
        """Fetch project metadata including status field and options.

        Args:
            owner: Override self.owner if provided
            project_number: Override self.project_number if provided

        Returns:
            ProjectInfo with project_id, status_field_id, status_options

        Raises:
            GitHubError: If project not found or query fails
        """
        owner = owner or self.owner
        project_number = project_number or self.project_number

        query = """
        query($owner: String!, $projectNumber: Int!) {
            user(login: $owner) {
                projectV2(number: $projectNumber) {
                    id
                    title
                    fields(first: 20) {
                        nodes {
                            ... on ProjectV2SingleSelectField {
                                id
                                name
                                options {
                                    id
                                    name
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        if self.owner_type == "organization":
            query = """
            query($owner: String!, $projectNumber: Int!) {
                organization(login: $owner) {
                    projectV2(number: $projectNumber) {
                        id
                        title
                        fields(first: 20) {
                            nodes {
                                ... on ProjectV2SingleSelectField {
                                    id
                                    name
                                    options {
                                        id
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """

        data = self._run_graphql(
            query, {"owner": owner, "projectNumber": project_number}
        )

        # Extract project node (user or organization)
        owner_node = data.get("user") or data.get("organization")
        if not owner_node:
            raise GitHubError(
                status_code=1,
                message=f"Owner '{owner}' not found (owner_type={self.owner_type})",
            )

        project = owner_node.get("projectV2")
        if not project:
            raise GitHubError(
                status_code=1,
                message=f"Project #{project_number} not found for owner '{owner}'",
            )

        project_id = project["id"]

        # Find Status field
        status_field_id = ""
        status_options: dict[str, str] = {}

        for field in project["fields"]["nodes"]:
            if field and field.get("name") == "Status":
                status_field_id = field["id"]
                for option in field.get("options", []):
                    status_options[option["name"]] = option["id"]
                break

        return ProjectInfo(
            project_id=project_id,
            status_field_id=status_field_id,
            status_options=status_options,
        )

    def add_item(self, project_id: str, content_id: str) -> str:
        """Add an issue/PR to project.

        Args:
            project_id: Project node ID (PVT_...)
            content_id: Issue/PR node ID (I_... or PR_...)

        Returns:
            Item ID (PVTI_...)

        Raises:
            GitHubError: If mutation fails
        """
        query = """
        mutation($projectId: ID!, $contentId: ID!) {
            addProjectV2ItemById(
                input: {projectId: $projectId, contentId: $contentId}
            ) {
                item {
                    id
                }
            }
        }
        """

        data = self._run_graphql(
            query, {"projectId": project_id, "contentId": content_id}
        )
        return cast(str, data["addProjectV2ItemById"]["item"]["id"])

    def update_item_status(
        self, project_id: str, item_id: str, status_field_id: str, option_id: str
    ) -> bool:
        """Update item's Status field value.

        Args:
            project_id: Project node ID
            item_id: Item node ID
            status_field_id: Status field ID
            option_id: Single select option ID

        Returns:
            True if update succeeded, False otherwise
        """
        query = """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
            updateProjectV2ItemFieldValue(
                input: {
                    projectId: $projectId
                    itemId: $itemId
                    fieldId: $fieldId
                    value: {singleSelectOptionId: $optionId}
                }
            ) {
                projectV2Item {
                    id
                }
            }
        }
        """

        data = self._run_graphql(
            query,
            {
                "projectId": project_id,
                "itemId": item_id,
                "fieldId": status_field_id,
                "optionId": option_id,
            },
        )

        # Success indicator: mutation returns non-null item
        return data["updateProjectV2ItemFieldValue"]["projectV2Item"] is not None

    def find_item_by_issue(self, project_id: str, issue_url: str) -> Item | None:
        """Find project item by issue URL.

        Args:
            project_id: Project node ID
            issue_url: Issue URL (https://github.com/owner/repo/issues/N)

        Returns:
            Item if found, None otherwise
        """
        for item_node in self._paginate_items(project_id):
            content = item_node.get("content")
            if content and content.get("url") == issue_url:
                # Extract status from fieldValue
                status = None
                field_value = item_node.get("fieldValue")
                if field_value and field_value.get("name"):
                    status = field_value["name"]

                return Item(
                    item_id=item_node["id"],
                    content=content,
                    status=status,
                )

        return None

    def _paginate_items(self, project_id: str, page_size: int = 50) -> Any:
        """Generator yielding all project items with cursor pagination.

        Args:
            project_id: Project node ID
            page_size: Items per page (default 50)

        Yields:
            Individual item nodes
        """
        cursor: str | None = None

        while True:
            query = """
            query($projectId: ID!, $first: Int!, $after: String) {
                node(id: $projectId) {
                    ... on ProjectV2 {
                        items(first: $first, after: $after) {
                            pageInfo {
                                hasNextPage
                                endCursor
                            }
                            nodes {
                                id
                                content {
                                    ... on Issue {
                                        title
                                        url
                                        number
                                    }
                                }
                                fieldValueByName(name: "Status") {
                                    ... on ProjectV2ItemFieldSingleSelectValue {
                                        name
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """

            variables = {"projectId": project_id, "first": page_size}
            if cursor:
                variables["after"] = cursor

            data = self._run_graphql(query, variables)

            items_data = data["node"]["items"]
            page_info = items_data["pageInfo"]

            for item_node in items_data["nodes"]:
                yield item_node

            if not page_info["hasNextPage"]:
                break

            cursor = page_info["endCursor"]
