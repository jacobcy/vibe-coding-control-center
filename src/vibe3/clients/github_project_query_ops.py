"""GitHub Projects v2 查询操作 mixin。"""

import json
import subprocess
from typing import Any, cast

from loguru import logger

from vibe3.models.project_item import ProjectItemData, ProjectItemError


class ProjectQueryMixin:
    """Mixin for GitHub Project read/query operations."""

    def find_item_by_issue(
        self: Any, issue_number: int
    ) -> ProjectItemData | ProjectItemError:
        """通过 issue number 反查关联的 Project item（支持分页）。"""
        if not self._get_token():
            return ProjectItemError(
                type="auth_error",
                message=(
                    "未找到 GitHub 认证令牌，"
                    "请设置 GITHUB_TOKEN 或运行 gh auth login"
                ),
            )

        owner_fragment, base_vars = self._owner_fragment()
        query = f"""
        query FindItemByIssue(
          $owner: String!, $projectNumber: Int!, $cursor: String
        ) {{
          {owner_fragment} {{
            projectV2(number: $projectNumber) {{
              items(first: 100, after: $cursor) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                  id
                  content {{
                    ... on Issue {{
                      number
                      title
                      body
                      assignees(first: 10) {{ nodes {{ login }} }}
                    }}
                  }}
                  fieldValues(first: 20) {{
                    nodes {{
                      ... on ProjectV2ItemFieldSingleSelectValue {{
                        name
                        field {{
                          ... on ProjectV2SingleSelectField {{ name }}
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """

        cursor: str | None = None
        while True:
            variables = {**base_vars, "cursor": cursor}
            try:
                data = self._run_graphql(query, variables)
            except subprocess.CalledProcessError as e:
                return ProjectItemError(
                    type="network_error", message=e.stderr or str(e)
                )
            except Exception as e:
                return ProjectItemError(type="network_error", message=str(e))

            try:
                data_root = data.get("data", {})
                project_data = None
                for key in ("user", "organization"):
                    if key in data_root:
                        project_data = data_root[key].get("projectV2", {})
                        break
                items_data = (project_data or {}).get("items", {})
                items = items_data.get("nodes", [])
                page_info = items_data.get("pageInfo", {})

                for item in items:
                    content = item.get("content") or {}
                    if content.get("number") == issue_number:
                        item_id = item["id"]
                        return cast(
                            "ProjectItemData",
                            self._parse_item_response(
                                {
                                    "data": {
                                        "organization": {
                                            "projectV2": {
                                                "item": {**item, "id": item_id}
                                            }
                                        }
                                    }
                                },
                                item_id,
                            ),
                        )

                if not page_info.get("hasNextPage"):
                    break
                cursor = page_info.get("endCursor")

            except Exception as e:
                raw = json.dumps(data)[:500]
                return ProjectItemError(
                    type="parse_error",
                    message=f"响应解析失败: {e}",
                    raw_response=raw,
                )

        return ProjectItemError(
            type="not_found",
            message=(f"Issue #{issue_number} 未关联到 Project {self.project_number}"),
        )

    def list_all_items(self: Any) -> list[dict[str, Any]] | ProjectItemError:
        """全量扫描 GitHub Project，返回所有 items 及其关联 issue/PR 信息。

        每个 item 包含：
        - id, content_type, content_number
        - head_ref_name: PR headRefName（仅 PR）
        - closing_issues: PR 关闭的 issue numbers（仅 PR）
        """
        if not self._get_token():
            return ProjectItemError(
                type="auth_error",
                message=(
                    "未找到 GitHub 认证令牌，"
                    "请设置 GITHUB_TOKEN 或运行 gh auth login"
                ),
            )

        owner_fragment, base_vars = self._owner_fragment()
        query = f"""
        query ListAllItems(
          $owner: String!, $projectNumber: Int!, $cursor: String
        ) {{
          {owner_fragment} {{
            projectV2(number: $projectNumber) {{
              items(first: 100, after: $cursor) {{
                pageInfo {{ hasNextPage endCursor }}
                nodes {{
                  id
                  content {{
                    ... on Issue {{
                      __typename
                      number
                      title
                    }}
                    ... on PullRequest {{
                      __typename
                      number
                      title
                      headRefName
                      closingIssuesReferences(first: 20) {{
                        nodes {{ number }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}
        """

        results: list[dict[str, Any]] = []
        cursor: str | None = None

        while True:
            variables = {**base_vars, "cursor": cursor}
            try:
                data = self._run_graphql(query, variables)
            except subprocess.CalledProcessError as e:
                return ProjectItemError(
                    type="network_error", message=e.stderr or str(e)
                )
            except Exception as e:
                return ProjectItemError(type="network_error", message=str(e))

            try:
                data_root = data.get("data", {})
                project_data = None
                for key in ("user", "organization"):
                    if key in data_root:
                        project_data = data_root[key].get("projectV2", {})
                        break
                items_data = (project_data or {}).get("items", {})
                nodes = items_data.get("nodes", [])
                page_info = items_data.get("pageInfo", {})

                for node in nodes:
                    content = node.get("content") or {}
                    typename = content.get("__typename")
                    item: dict[str, Any] = {
                        "id": node.get("id"),
                        "content_type": typename,
                        "content_number": content.get("number"),
                        "head_ref_name": None,
                        "closing_issues": [],
                    }
                    if typename == "PullRequest":
                        item["head_ref_name"] = content.get("headRefName")
                        closing = content.get("closingIssuesReferences", {}).get(
                            "nodes", []
                        )
                        item["closing_issues"] = [
                            n["number"] for n in closing if n.get("number")
                        ]
                    results.append(item)

                if not page_info.get("hasNextPage"):
                    break
                cursor = page_info.get("endCursor")

            except Exception as e:
                raw = json.dumps(data)[:500]
                return ProjectItemError(
                    type="parse_error",
                    message=f"响应解析失败: {e}",
                    raw_response=raw,
                )

        logger.bind(
            domain="github_project",
            operation="list_all_items",
            count=len(results),
        ).info("Fetched all project items")
        return results
