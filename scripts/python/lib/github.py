import subprocess
import json

class GitHubHelper:
    @staticmethod
    def list_issues(limit=30, state="open"):
        cmd = ["gh", "issue", "list", "--limit", str(limit), "--state", state, "--json", "number,title,state,updatedAt,labels"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error calling gh: {result.stderr}")
            return []
        return json.loads(result.stdout)

    @staticmethod
    def view_issue(issue_number):
        cmd = ["gh", "issue", "view", str(issue_number), "--json", "number,title,body,state,updatedAt,labels,comments"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error calling gh: {result.stderr}")
            return None
        return json.loads(result.stdout)
