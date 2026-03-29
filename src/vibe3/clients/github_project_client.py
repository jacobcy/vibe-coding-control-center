"""GitHub Projects v2 客户端。

通过 gh api graphql 与 GitHub Projects v2 GraphQL API 交互。
org 和 project_number 从 config/settings.yaml 读取，不支持命令行动态传入。
"""

import json
import os
import subprocess
from typing import Any

from loguru import logger

from vibe3.clients.github_client_base import GitHubClientBase
from vibe3.clients.github_project_mutation_ops import ProjectMutationMixin
from vibe3.clients.github_project_query_ops import ProjectQueryMixin
from vibe3.models.project_item import ProjectItemData, ProjectItemError


class GitHubProjectClient(GitHubClientBase, ProjectQueryMixin, ProjectMutationMixin):
    """GitHub Projects v2 客户端。

    负责读取和更新 GitHub Projects v2 中的 Project item（task 真源）。
    - ProjectQueryMixin: find_item_by_issue, list_all_items
    - ProjectMutationMixin: update_item_status
    """

    def __init__(
        self,
        org: str,
        project_number: int,
        owner_type: str = "org",
        owner: str = "",
    ) -> None:
        """初始化客户端。

        Args:
            org: 已废弃，请使用 owner 参数
            project_number: GitHub Project number
            owner_type: "org" 或 "user"
            owner: GitHub 组织名或用户名（优先于 org）
        """
        self.owner = owner or org
        self.org = self.owner  # 向后兼容
        self.owner_type = owner_type
        self.project_number = project_number

    def _get_token(self) -> str | None:
        """获取 GitHub 认证令牌。"""
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            return token
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"GitHub auth token retrieval failed: {e}")
        return None

    def _run_graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """执行 GraphQL 查询。"""
        payload = json.dumps({"query": query, "variables": variables})
        result = subprocess.run(
            ["gh", "api", "graphql", "--input", "-"],
            input=payload,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                "gh api graphql",
                result.stdout,
                result.stderr,
            )
        return json.loads(result.stdout)  # type: ignore[no-any-return]

    def _owner_fragment(self) -> tuple[str, dict[str, Any]]:
        """返回 GraphQL owner 查询片段和对应变量。"""
        if self.owner_type == "user":
            fragment = "user(login: $owner)"
        else:
            fragment = "organization(login: $owner)"
        return fragment, {
            "owner": self.owner,
            "projectNumber": self.project_number,
        }

    def get_item(self, project_item_id: str) -> ProjectItemData | ProjectItemError:
        """从 GitHub Project 读取 item 数据（通过 node ID 直接查询）。"""
        if not self._get_token():
            return ProjectItemError(
                type="auth_error",
                message=(
                    "未找到 GitHub 认证令牌，请设置 GH_TOKEN 或运行 gh auth login"
                ),
            )

        query = """
        query GetProjectItem($itemId: ID!) {
          node(id: $itemId) {
            ... on ProjectV2Item {
              id
              content {
                ... on Issue {
                  title
                  body
                  assignees(first: 10) { nodes { login } }
                }
              }
              fieldValues(first: 20) {
                nodes {
                  ... on ProjectV2ItemFieldSingleSelectValue {
                    name
                    field { ... on ProjectV2SingleSelectField { name } }
                  }
                }
              }
            }
          }
        }
        """
        try:
            data = self._run_graphql(query, {"itemId": project_item_id})
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr or str(e)
            if "401" in err_msg or "authentication" in err_msg.lower():
                return ProjectItemError(type="auth_error", message=err_msg)
            return ProjectItemError(type="network_error", message=err_msg)
        except Exception as e:
            return ProjectItemError(type="network_error", message=str(e))

        try:
            return self._parse_node_response(data, project_item_id)
        except Exception as e:
            raw = json.dumps(data)[:500]
            logger.bind(domain="github_project", operation="get_item").error(
                f"Failed to parse response: {e}"
            )
            return ProjectItemError(
                type="parse_error",
                message=f"响应解析失败: {e}",
                raw_response=raw,
            )

    def _parse_node_response(
        self, data: dict[str, Any], item_id: str
    ) -> ProjectItemData:
        """解析 node(id:) 查询响应为 ProjectItemData。"""
        node = data.get("data", {}).get("node")
        if not node:
            raise ValueError("响应中未找到 node 数据")

        node_id = node.get("id", "")
        content = node.get("content") or {}
        title = content.get("title")
        body = content.get("body")
        assignees_nodes = content.get("assignees", {}).get("nodes", [])
        assignees = [n["login"] for n in assignees_nodes if n.get("login")]

        status: str | None = None
        priority: str | None = None
        for fv in node.get("fieldValues", {}).get("nodes", []):
            field_name = (fv.get("field") or {}).get("name", "").lower()
            value_name = fv.get("name")
            if field_name == "status":
                status = value_name
            elif field_name == "priority":
                priority = value_name

        return ProjectItemData(
            item_id=item_id,
            node_id=node_id,
            title=title,
            body=body,
            status=status,
            priority=priority,
            assignees=assignees,
            partial=not bool(title),
        )

    def _parse_item_response(
        self, data: dict[str, Any], item_id: str
    ) -> ProjectItemData:
        """解析 projectV2.item 查询响应为 ProjectItemData。"""
        item = None
        data_root = data.get("data", {})
        for key in ("user", "organization"):
            if key in data_root:
                item = data_root[key].get("projectV2", {}).get("item")
                break

        if not item:
            raise ValueError("响应中未找到 item 数据")

        node_id = item.get("id", "")
        content = item.get("content") or {}
        title = content.get("title")
        body = content.get("body")
        assignees_nodes = content.get("assignees", {}).get("nodes", [])
        assignees = [n["login"] for n in assignees_nodes if n.get("login")]

        status: str | None = None
        priority: str | None = None
        for fv in item.get("fieldValues", {}).get("nodes", []):
            field_name = (fv.get("field") or {}).get("name", "").lower()
            value_name = fv.get("name")
            if field_name == "status":
                status = value_name
            elif field_name == "priority":
                priority = value_name

        return ProjectItemData(
            item_id=item_id,
            node_id=node_id,
            title=title,
            body=body,
            status=status,
            priority=priority,
            assignees=assignees,
            partial=not bool(title),
        )
