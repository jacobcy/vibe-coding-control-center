import subprocess
import os
import sys
import json

# Add lib to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.store import Vibe3Store
from lib.github import GitHubHelper

class AuditManager:
    def __init__(self, json_output=False):
        self.store = Vibe3Store()
        self.json_output = json_output

    def _get_current_branch(self):
        return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()

    def check(self):
        print("Running Vibe 3.0 Consistency Audit...")
        branch = self._get_current_branch()
        errors = 0
        warnings = 0

        # 1. Check DB record
        state = self.store.get_flow_state(branch)
        if not state:
            print(f"❌ [Error] No V3 flow record found for current branch: {branch}")
            errors += 1
        else:
            print(f"✅ [OK] Flow record found: {state['flow_slug']}")

        # 2. Check Task Binding
        if state and state.get('task_issue_number'):
            print(f"✅ [OK] Flow bound to task issue #{state['task_issue_number']}")
            # Verify remote
            issue = GitHubHelper.view_issue(state['task_issue_number'])
            if not issue:
                print(f"❌ [Error] Bound task issue #{state['task_issue_number']} not found on GitHub")
                errors += 1
            else:
                print(f"✅ [OK] Task issue verified on GitHub: {issue['title']}")
        else:
            print("⚠️ [Warning] No primary task issue bound to current flow")
            warnings += 1

        # 3. Check PR
        if state and state.get('pr_number'):
            print(f"✅ [OK] Flow bound to PR #{state['pr_number']}")
            # Verify remote
            try:
                cmd = ["gh", "pr", "view", str(state['pr_number']), "--json", "number,state"]
                subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"✅ [OK] PR verified on GitHub")
            except subprocess.CalledProcessError:
                print(f"❌ [Error] Bound PR #{state['pr_number']} not found or error fetching")
                errors += 1
        else:
            # Check if there is a PR on GH but not in DB
            try:
                cmd = ["gh", "pr", "view", "--json", "number"]
                output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
                import json
                pr_num = json.loads(output)['number']
                print(f"⚠️ [Warning] Found PR #{pr_num} for this branch on GitHub, but not recorded in handoff.db")
                warnings += 1
            except:
                pass

        # 4. Check task.md
        task_md_path = os.path.join(os.getcwd(), '.agent/context/task.md')
        if os.path.exists(task_md_path):
            print("✅ [OK] Local task.md exists")
            # Potential check for task id in task.md
            with open(task_md_path, 'r') as f:
                content = f.read()
                if state and state.get('task_issue_number'):
                    issue_str = f"#{state['task_issue_number']}"
                    if issue_str not in content:
                        print(f"⚠️ [Warning] task.md does not contain bound task ID {issue_str}")
                        warnings += 1
        else:
            print("⚠️ [Warning] No local task.md found (handoff missing)")
            warnings += 1

        print("-" * 20)
        print(f"Audit Complete: {errors} Errors, {warnings} Warnings")
        if errors > 0:
            sys.exit(1)
