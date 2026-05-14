"""Integration tests for GitHubProjectClient against real gh CLI."""

import subprocess

import pytest

from vibe3.clients.github_project_client import GitHubProjectClient
from vibe3.models.github_project import ProjectInfo

# Skip all tests if gh CLI unavailable or lacks project scope
pytestmark = pytest.mark.integration


def _check_gh_available() -> bool:
    """Check if gh CLI is available and has project scope."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
        )
        # gh auth status returns exit code 1 when keyring is invalid but token is valid
        # Check for project scope in combined output
        output = result.stdout + result.stderr
        return "project" in output
    except FileNotFoundError:
        return False


# Module-level skip
if not _check_gh_available():
    pytest.skip("gh CLI not available or lacks project scope", allow_module_level=True)


# Test constants (from verified environment)
OWNER = "jacobcy"
PROJECT_NUMBER = 17
TEST_ISSUE_REPO = "jacobcy/vibe-coding-control-center"


@pytest.fixture
def client() -> GitHubProjectClient:
    """Create client instance."""
    return GitHubProjectClient(OWNER, PROJECT_NUMBER)


@pytest.fixture
def project_info(client: GitHubProjectClient) -> ProjectInfo:
    """Get project info for test project."""
    return client.get_project_info()


def test_get_project_info(client: GitHubProjectClient) -> None:
    """Test fetching project metadata."""
    info = client.get_project_info()

    assert info.project_id.startswith("PVT_")
    assert info.status_field_id.startswith("PVTSSF_")
    assert len(info.status_options) >= 3
    assert "Todo" in info.status_options
    assert "In Progress" in info.status_options
    assert "Done" in info.status_options


def test_add_item(client: GitHubProjectClient, project_info: ProjectInfo) -> None:
    """Test adding issue to project."""
    # Find an existing issue in test repo
    query = """
    query($owner: String!, $repo: String!, $number: Int!) {
        repository(owner: $owner, name: $repo) {
            issue(number: $number) {
                id
            }
        }
    }
    """

    # Use issue #753 (this issue itself) as test content
    result = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"owner={OWNER}",
            "-F",
            f"repo={TEST_ISSUE_REPO.split('/')[-1]}",
            "-F",
            "number=753",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    import json

    data = json.loads(result.stdout)
    content_id = data["data"]["repository"]["issue"]["id"]

    # Add item
    item_id = ""
    try:
        item_id = client.add_item(project_info.project_id, content_id)

        assert item_id.startswith("PVTI_")

    finally:
        # Cleanup: delete test item
        if item_id:
            delete_query = """
            mutation($projectId: ID!, $itemId: ID!) {
                deleteProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) {
                    deletedItemId
                }
            }
            """
            subprocess.run(
                [
                    "gh",
                    "api",
                    "graphql",
                    "-f",
                    f"query={delete_query}",
                    "-F",
                    f"projectId={project_info.project_id}",
                    "-F",
                    f"itemId={item_id}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )


def test_update_item_status(
    client: GitHubProjectClient, project_info: ProjectInfo
) -> None:
    """Test updating item status field."""
    # Get test issue node ID
    query = """
    query($owner: String!, $repo: String!, $number: Int!) {
        repository(owner: $owner, name: $repo) {
            issue(number: $number) {
                id
            }
        }
    }
    """

    result = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"owner={OWNER}",
            "-F",
            f"repo={TEST_ISSUE_REPO.split('/')[-1]}",
            "-F",
            "number=753",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    import json

    data = json.loads(result.stdout)
    content_id = data["data"]["repository"]["issue"]["id"]

    item_id = ""
    try:
        # Add test item
        item_id = client.add_item(project_info.project_id, content_id)

        # Update status to "Todo"
        todo_option_id = project_info.status_options["Todo"]
        success = client.update_item_status(
            project_info.project_id,
            item_id,
            project_info.status_field_id,
            todo_option_id,
        )

        assert success is True

        # Verify update via follow-up query
        verify_query = """
        query($itemId: ID!) {
            node(id: $itemId) {
                ... on ProjectV2Item {
                    fieldValueByName(name: "Status") {
                        ... on ProjectV2ItemFieldSingleSelectValue {
                            name
                        }
                    }
                }
            }
        }
        """

        verify_result = subprocess.run(
            [
                "gh",
                "api",
                "graphql",
                "-f",
                f"query={verify_query}",
                "-F",
                f"itemId={item_id}",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        verify_data = json.loads(verify_result.stdout)
        status_name = verify_data["data"]["node"]["fieldValueByName"]["name"]
        assert status_name == "Todo"

    finally:
        # Cleanup
        if item_id:
            delete_query = """
            mutation($projectId: ID!, $itemId: ID!) {
                deleteProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) {
                    deletedItemId
                }
            }
            """
            subprocess.run(
                [
                    "gh",
                    "api",
                    "graphql",
                    "-f",
                    f"query={delete_query}",
                    "-F",
                    f"projectId={project_info.project_id}",
                    "-F",
                    f"itemId={item_id}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )


def test_find_item_by_issue(
    client: GitHubProjectClient, project_info: ProjectInfo
) -> None:
    """Test finding project item by issue URL."""
    # Get test issue node ID
    query = """
    query($owner: String!, $repo: String!, $number: Int!) {
        repository(owner: $owner, name: $repo) {
            issue(number: $number) {
                id
            }
        }
    }
    """

    result = subprocess.run(
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-F",
            f"owner={OWNER}",
            "-F",
            f"repo={TEST_ISSUE_REPO.split('/')[-1]}",
            "-F",
            "number=753",
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    import json

    data = json.loads(result.stdout)
    content_id = data["data"]["repository"]["issue"]["id"]

    issue_url = f"https://github.com/{TEST_ISSUE_REPO}/issues/753"
    item_id = ""

    try:
        # Add test item
        item_id = client.add_item(project_info.project_id, content_id)

        # Find by issue URL
        item = client.find_item_by_issue(project_info.project_id, issue_url)

        assert item is not None
        assert item.item_id == item_id
        assert item.content["url"] == issue_url

    finally:
        # Cleanup
        if item_id:
            delete_query = """
            mutation($projectId: ID!, $itemId: ID!) {
                deleteProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) {
                    deletedItemId
                }
            }
            """
            subprocess.run(
                [
                    "gh",
                    "api",
                    "graphql",
                    "-f",
                    f"query={delete_query}",
                    "-F",
                    f"projectId={project_info.project_id}",
                    "-F",
                    f"itemId={item_id}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )


def test_find_item_by_issue_not_found(
    client: GitHubProjectClient, project_info: ProjectInfo
) -> None:
    """Test finding item with non-existent issue URL."""
    fake_url = "https://github.com/fake/repo/issues/999"

    item = client.find_item_by_issue(project_info.project_id, fake_url)

    assert item is None
