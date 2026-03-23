"""GitHub Projects v2 写操作 mixin。"""

import subprocess
from typing import Any

from loguru import logger

from vibe3.models.project_item import ProjectItemError


class ProjectMutationMixin:
    """Mixin for GitHub Project write/mutation operations."""

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
