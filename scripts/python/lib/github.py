import json
import subprocess
from typing import Any


class GitHubHelper:
    @staticmethod
    def list_issues(limit: int = 30, state: str = "open") -> list[dict[str, Any]]:
        cmd = [
            "gh",
            "issue",
            "list",
            "--limit",
            str(limit),
            "--state",
            state,
            "--json",
            "number,title,state,updatedAt,labels",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error calling gh: {result.stderr}")
            return []
        return json.loads(result.stdout)  # type: ignore

    @staticmethod
    def view_issue(issue_number: int) -> dict[str, Any] | None:
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "number,title,body,state,updatedAt,labels,comments",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error calling gh: {result.stderr}")
            return None
        return json.loads(result.stdout)  # type: ignore
