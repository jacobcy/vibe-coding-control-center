import subprocess
import os
import sys
import json

# Add lib to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.store import Vibe3Store
from lib.github import GitHubHelper

class PRManager:
    def __init__(self, json_output=False, auto_confirm=False):
        self.store = Vibe3Store()
        self.json_output = json_output
        self.auto_confirm = auto_confirm

    def _get_current_branch(self):
        return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()

    def draft(self, title=None, body=None):
        branch = self._get_current_branch()
        state = self.store.get_flow_state(branch)
        
        if not title:
            if state and state.get('task_issue_number'):
                issue = GitHubHelper.view_issue(state['task_issue_number'])
                if issue:
                    title = f"feat: {issue['title']} (#{issue['number']})"
            if not title:
                title = f"Draft PR for {branch}"

        if not body:
            body = "Automatically created by Vibe 3.0"
            if state and state.get('task_issue_number'):
                body += f"\n\nCloses #{state['task_issue_number']}"

        print(f"Creating Draft PR: {title}")
        cmd = ["gh", "pr", "create", "--draft", "--title", title, "--body", body]
        try:
            output = subprocess.check_output(cmd).decode().strip()
            pr_url = output
            pr_number = pr_url.split('/')[-1]
            print(f"Created Draft PR: {pr_url}")
            
            # Update store
            self.store.update_flow_state(branch, pr_number=int(pr_number))
            return pr_number
        except subprocess.CalledProcessError as e:
            print(f"Error creating PR: {e}")
            return None

    def show(self):
        branch = self._get_current_branch()
        state = self.store.get_flow_state(branch)
        
        pr_number = None
        if state and state.get('pr_number'):
            pr_number = state['pr_number']
        
        if not pr_number:
            # Try to find PR for current branch via gh
            try:
                cmd = ["gh", "pr", "view", "--json", "number,url,state,title,isDraft"]
                output = subprocess.check_output(cmd).decode().strip()
                pr = json.loads(output)
                pr_number = pr['number']
                # Sync back to store
                self.store.update_flow_state(branch, pr_number=pr_number)
            except:
                print("No PR found for current branch.")
                return



        cmd = ["gh", "pr", "view", str(pr_number), "--json", "number,title,state,url,isDraft,mergeable,reviews"]
        try:
            output = subprocess.check_output(cmd).decode().strip()
            pr = json.loads(output)
            print(f"PR #{pr['number']}: {pr['title']}")
            print(f"State: {pr['state']} {'(Draft)' if pr['isDraft'] else ''}")
            print(f"Mergeable: {pr['mergeable']}")
            print(f"URL: {pr['url']}")
        except subprocess.CalledProcessError:
            print(f"Failed to fetch PR #{pr_number}")


    def ready(self):
        branch = self._get_current_branch()
        state = self.store.get_flow_state(branch)
        if not state or not state.get('pr_number'):
            print("Error: No PR bound to current flow.")
            return

        print(f"Marking PR #{state['pr_number']} as ready for review...")
        cmd = ["gh", "pr", "ready", str(state['pr_number'])]
        try:
            subprocess.check_call(cmd)
            print("PR is now ready.")
        except subprocess.CalledProcessError as e:
            print(f"Error: {e}")

    def merge(self):
        branch = self._get_current_branch()
        state = self.store.get_flow_state(branch)
        if not state or not state.get('pr_number'):
            print("Error: No PR bound to current flow.")
            return

        print(f"Merging PR #{state['pr_number']}...")
        # Use squash merge by default as per common patterns
        cmd = ["gh", "pr", "merge", str(state['pr_number']), "--squash", "--delete-branch"]
        try:
            subprocess.check_call(cmd)
            print("Merged successfully.")
            # Update flow status in DB
            self.store.update_flow_state(branch, flow_status='merged')
        except subprocess.CalledProcessError as e:
            print(f"Error merging PR: {e}")
