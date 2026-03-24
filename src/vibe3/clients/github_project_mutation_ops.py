"""GitHub Projects v2 写操作 mixin。"""

import subprocess
from typing import Any

from loguru import logger

from vibe3.models.project_item import ProjectItemData, ProjectItemError


class ProjectMutationMixin:
    """Mixin for GitHub Project write/mutation operations."""

    def _get_repo_name(self: Any) -> str | None:
        """动态获取当前 git repo 名称。"""
        try:
            result = subprocess.run(
                ["gh", "repo", "view", "--json", "name", "--jq", ".name"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def add_issue_to_project(
        self: Any, issue_number: int
    ) -> ProjectItemData | ProjectItemError:
        """将 issue 添加到 GitHub Project，返回新建的 ProjectItemData。

        自动获取 project node_id 及 issue content node_id，
        通过 addProjectV2ItemById mutation 完成操作。
        """
        if not self._get_token():
            return ProjectItemError(
                type="auth_error",
                message="未找到 GitHub 认证令牌，请设置 GH_TOKEN 或运行 gh auth login",
            )

        # Step 1: 获取 project node_id
        owner_fragment, meta_vars = self._owner_fragment()
        project_id_query = f"""
        query GetProjectId($owner: String!, $projectNumber: Int!) {{
          {owner_fragment} {{
            projectV2(number: $projectNumber) {{
              id
            }}
          }}
        }}
        """
        try:
            meta = self._run_graphql(project_id_query, meta_vars)
        except Exception as e:
            return ProjectItemError(type="network_error", message=str(e))

        project_id = None
        for key in ("user", "organization"):
            if key in meta.get("data", {}):
                project_id = meta["data"][key].get("projectV2", {}).get("id")
                break

        if not project_id:
            return ProjectItemError(
                type="not_found", message="无法获取 GitHub Project node ID"
            )

        # Step 2: 获取 issue content node_id
        repo_name = self._get_repo_name()
        if not repo_name:
            return ProjectItemError(
                type="network_error", message="无法自动获取 repo 名称"
            )

        issue_id_query = """
        query GetIssueId($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            issue(number: $number) {
              id
            }
          }
        }
        """
        try:
            issue_data = self._run_graphql(
                issue_id_query,
                {"owner": self.owner, "repo": repo_name, "number": issue_number},
            )
        except Exception as e:
            return ProjectItemError(type="network_error", message=str(e))

        content_id = (
            issue_data.get("data", {}).get("repository", {}).get("issue", {}).get("id")
        )
        if not content_id:
            return ProjectItemError(
                type="not_found",
                message=(
                    f"Issue #{issue_number} 在仓库 "
                    f"{self.owner}/{repo_name} 中未找到"
                ),
            )

        # Step 3: 通过 addProjectV2ItemById 将 issue 加入 project
        add_mutation = """
        mutation AddIssueToProject($projectId: ID!, $contentId: ID!) {
          addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
            item {
              id
            }
          }
        }
        """
        try:
            result = self._run_graphql(
                add_mutation,
                {"projectId": project_id, "contentId": content_id},
            )
        except subprocess.CalledProcessError as e:
            return ProjectItemError(type="network_error", message=e.stderr or str(e))
        except Exception as e:
            return ProjectItemError(type="network_error", message=str(e))

        item_id = (
            result.get("data", {})
            .get("addProjectV2ItemById", {})
            .get("item", {})
            .get("id")
        )
        if not item_id:
            return ProjectItemError(
                type="parse_error",
                message="addProjectV2ItemById 成功但未返回 item ID",
            )

        logger.bind(
            domain="github_project",
            operation="add_issue_to_project",
            issue_number=issue_number,
            item_id=item_id,
        ).info("Added issue to project")
        return ProjectItemData(item_id=item_id, node_id=item_id, partial=True)

    def update_item_status(
        self: Any, node_id: str, status_value: str
    ) -> bool | ProjectItemError:
        """更新 Project item 的 status 字段。

        通过 GraphQL mutation 更新远端 GitHub Project item 状态。
        这是唯一合法的 task 状态写入路径，本地 SQLite 不存储 task 状态。
        """
        if not self._get_token():
            return ProjectItemError(
                type="auth_error",
                message=(
                    "未找到 GitHub 认证令牌，请设置 GH_TOKEN 或运行 gh auth login"
                ),
            )

        owner_fragment, meta_vars = self._owner_fragment()
        meta_query = f"""
        query GetProjectMeta($owner: String!, $projectNumber: Int!) {{
          {owner_fragment} {{
            projectV2(number: $projectNumber) {{
              id
              fields(first: 20) {{
                nodes {{
                  ... on ProjectV2SingleSelectField {{
                    id
                    name
                    options {{ id name }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """
        try:
            meta = self._run_graphql(meta_query, meta_vars)
        except Exception as e:
            return ProjectItemError(type="network_error", message=str(e))

        try:
            meta_root = meta.get("data", {})
            project = None
            for key in ("user", "organization"):
                if key in meta_root:
                    project = meta_root[key].get("projectV2", {})
                    break
            project = project or {}
            project_id = project.get("id")
            status_field = None
            option_id = None

            for field in project.get("fields", {}).get("nodes", []):
                if field.get("name", "").lower() == "status":
                    status_field = field
                    for opt in field.get("options", []):
                        if opt.get("name", "").lower() == status_value.lower():
                            option_id = opt["id"]
                            break
                    break

            if not status_field or not option_id:
                return ProjectItemError(
                    type="not_found",
                    message=f"未找到 status 字段或选项 '{status_value}'",
                )
        except Exception as e:
            return ProjectItemError(type="parse_error", message=str(e))

        mutation = """
        mutation UpdateItemStatus(
          $projectId: ID!
          $itemId: ID!
          $fieldId: ID!
          $optionId: String!
        ) {
          updateProjectV2ItemFieldValue(input: {
            projectId: $projectId
            itemId: $itemId
            fieldId: $fieldId
            value: { singleSelectOptionId: $optionId }
          }) {
            projectV2Item { id }
          }
        }
        """
        try:
            self._run_graphql(
                mutation,
                {
                    "projectId": project_id,
                    "itemId": node_id,
                    "fieldId": status_field["id"],
                    "optionId": option_id,
                },
            )
            logger.bind(
                domain="github_project",
                operation="update_item_status",
                node_id=node_id,
                status=status_value,
            ).info("Updated remote task status")
            return True
        except subprocess.CalledProcessError as e:
            return ProjectItemError(type="network_error", message=e.stderr or str(e))
        except Exception as e:
            return ProjectItemError(type="network_error", message=str(e))
