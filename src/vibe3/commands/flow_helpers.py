#!/usr/bin/env python3
"""Flow command helper functions."""

from contextlib import contextmanager
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from vibe3.clients.github_client import GitHubClient
    from vibe3.models.flow import FlowStatusResponse


@contextmanager
def _noop() -> Iterator[None]:
    yield


def fetch_issue_titles(
    gh: "GitHubClient", flow_status: "FlowStatusResponse"
) -> tuple[dict[int, str], "dict[str, object] | None", bool]:
    """拉取 flow 关联 issue title 和 PR 信息。network_error=True 表示网络故障。"""
    titles: dict[int, str] = {}
    network_error = False
    numbers: set[int] = set()
    if flow_status.task_issue_number:
        numbers.add(flow_status.task_issue_number)
    for link in flow_status.issues:
        numbers.add(link.issue_number)

    for n in numbers:
        result = gh.view_issue(n)
        if result == "network_error":
            network_error = True
            break
        if isinstance(result, dict):
            titles[n] = result.get("title", "")

    pr_data: dict[str, object] | None = None
    if flow_status.pr_number and not network_error:
        try:
            pr = gh.get_pr(flow_status.pr_number)
            if pr:
                pr_data = {
                    "number": pr.number,
                    "title": pr.title,
                    "state": pr.state.value,
                    "draft": pr.draft,
                    "url": pr.url,
                }
        except Exception:
            network_error = True

    return titles, pr_data, network_error
