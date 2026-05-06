"""GitHub Projects GraphQL API client.

Provides operations for GitHub Projects v2 (the new project board).
Uses `gh api graphql` for all operations.
"""

import json
import subprocess

from loguru import logger

from vibe3.exceptions import GitHubError


class GitHubProjectClient:
    """Client for GitHub Projects v2 GraphQL API operations.

    Token Management:
        Relies on environment variable GH_TOKEN, same as GitHubClientBase.
        The token should have `project` scope for write operations.

    Configuration:
        Requires owner (user/org) and project_number from settings.yaml.
    """

    def __init__(
        self, owner: str, project_number: int, owner_type: str = "user"
    ) -> None:
        """Initialize the GitHub Project client.

        Args:
            owner: GitHub user or org name (e.g., "jacobcy" or "myorg")
            project_number: Project number (visible in project URL)
            owner_type: "user" or "org" (default: "user")
        """
        self.owner = owner
        self.project_number = project_number
        self.owner_type = owner_type

    def get_project_id(self) -> str:
        """Get the GraphQL ID of the project.

        Returns:
            Project node ID (e.g., "PVT_...")

        Raises:
            GitHubError: If project not found or API error
        """
        # Build query based on owner_type
        if self.owner_type == "org":
            owner_field = "organization"
        else:
            owner_field = "user"

        query = f"""
        query($owner: String!, $number: Int!) {{
            {owner_field}(login: $owner) {{
                projectV2(number: $number) {{
                    id
                }}
            }}
        }}
        """

        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    "graphql",
                    "-f",
                    f"query={query}",
                    "-f",
                    f"owner={self.owner}",
                    "-F",
                    f"number={self.project_number}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            data = json.loads(result.stdout)
            project_id = (
                data.get("data", {}).get(owner_field, {}).get("projectV2", {}).get("id")
            )

            if not project_id:
                raise GitHubError(
                    status_code=404,
                    message=(
                        f"Project #{self.project_number} not found "
                        f"for {self.owner_type} {self.owner}"
                    ),
                )

            return str(project_id)

        except subprocess.CalledProcessError as e:
            error_msg = (e.stderr or e.stdout or str(e)).strip()
            raise GitHubError(
                status_code=e.returncode,
                message=f"Failed to get project ID: {error_msg}",
            ) from e
        except json.JSONDecodeError as e:
            raise GitHubError(
                status_code=500,
                message=f"Failed to parse project ID response: {e}",
            ) from e

    def find_item_by_issue(self, issue_number: int) -> str | None:
        """Find the project item ID for a given issue number.

        Args:
            issue_number: GitHub issue number

        Returns:
            Project item ID (e.g., "PVTI_...") or None if not found

        Raises:
            GitHubError: If API error occurs
        """
        # Build query based on owner_type
        if self.owner_type == "org":
            owner_field = "organization"
        else:
            owner_field = "user"

        query = f"""
        query($owner: String!, $number: Int!) {{
            {owner_field}(login: $owner) {{
                projectV2(number: $number) {{
                    items(first: 100) {{
                        nodes {{
                            id
                            content {{
                                ... on Issue {{
                                    number
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """

        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    "graphql",
                    "-f",
                    f"query={query}",
                    "-f",
                    f"owner={self.owner}",
                    "-F",
                    f"number={self.project_number}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            data = json.loads(result.stdout)
            items = (
                data.get("data", {})
                .get(owner_field, {})
                .get("projectV2", {})
                .get("items", {})
                .get("nodes", [])
            )

            for item in items:
                content = item.get("content", {})
                if content and content.get("number") == issue_number:
                    item_id = item.get("id")
                    if item_id:
                        return str(item_id)

            return None

        except subprocess.CalledProcessError as e:
            error_msg = (e.stderr or e.stdout or str(e)).strip()
            raise GitHubError(
                status_code=e.returncode,
                message=f"Failed to find item for issue #{issue_number}: {error_msg}",
            ) from e
        except json.JSONDecodeError as e:
            raise GitHubError(
                status_code=500,
                message=f"Failed to parse items response: {e}",
            ) from e

    def update_item_status(
        self,
        item_id: str,
        status_value: str,
        status_field_name: str = "Status",
    ) -> None:
        """Update the Status field of a project item.

        Args:
            item_id: Project item ID (e.g., "PVTI_...")
            status_value: New status value (e.g., "Ready", "In Progress")
            status_field_name: Field name (default: "Status")

        Raises:
            GitHubError: If update fails
        """
        project_id = self.get_project_id()

        # First, find the Status field ID
        field_query = """
        query($projectId: ID!) {
            node(id: $projectId) {
                ... on ProjectV2 {
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

        try:
            result = subprocess.run(
                [
                    "gh",
                    "api",
                    "graphql",
                    "-f",
                    f"query={field_query}",
                    "-f",
                    f"projectId={project_id}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            data = json.loads(result.stdout)
            fields = (
                data.get("data", {}).get("node", {}).get("fields", {}).get("nodes", [])
            )

            # Find the Status field
            status_field = None
            status_option_id = None
            for field in fields:
                if field.get("name") == status_field_name:
                    status_field = field
                    options = field.get("options", [])
                    for option in options:
                        if option.get("name") == status_value:
                            status_option_id = option.get("id")
                            break
                    break

            if not status_field:
                logger.bind(
                    domain="github_project",
                    operation="update_item_status",
                    item_id=item_id,
                    status_field_name=status_field_name,
                ).warning(f"Field '{status_field_name}' not found in project")
                return

            if not status_option_id:
                logger.bind(
                    domain="github_project",
                    operation="update_item_status",
                    item_id=item_id,
                    status_value=status_value,
                    status_field_name=status_field_name,
                ).warning(f"Status value '{status_value}' not found in field options")
                return

            # Update the item
            mutation = """
            mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: ID!) {
                updateProjectV2ItemFieldValue(
                    input: {
                        projectId: $projectId
                        itemId: $itemId
                        fieldId: $fieldId
                        value: { singleSelectOptionId: $optionId }
                    }
                ) {
                    projectV2Item {
                        id
                    }
                }
            }
            """

            subprocess.run(
                [
                    "gh",
                    "api",
                    "graphql",
                    "-f",
                    f"query={mutation}",
                    "-f",
                    f"projectId={project_id}",
                    "-f",
                    f"itemId={item_id}",
                    "-f",
                    f"fieldId={status_field['id']}",
                    "-f",
                    f"optionId={status_option_id}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            logger.bind(
                domain="github_project",
                operation="update_item_status",
                item_id=item_id,
                status_value=status_value,
            ).info(f"Updated project item status to '{status_value}'")

        except subprocess.CalledProcessError as e:
            error_msg = (e.stderr or e.stdout or str(e)).strip()
            raise GitHubError(
                status_code=e.returncode,
                message=f"Failed to update item status: {error_msg}",
            ) from e
        except json.JSONDecodeError as e:
            raise GitHubError(
                status_code=500,
                message=f"Failed to parse field/update response: {e}",
            ) from e
