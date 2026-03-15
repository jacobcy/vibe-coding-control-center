import subprocess
import os
import sys
import json

# Add lib to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.store import Vibe3Store

class FlowManager:
    def __init__(self, json_output=False, auto_confirm=False):
        self.store = Vibe3Store()
        self.json_output = json_output
        self.auto_confirm = auto_confirm

    def _get_current_branch(self):
        return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()

    def show(self, branch=None):
        if not branch:
            branch = self._get_current_branch()
        
        state = self.store.get_flow_state(branch)
        if not state:
            print(f"No v3 flow record found for branch: {branch}")
            return

        print(f"Flow: {state['flow_slug']}")
        print(f"Title: {state.get('title', 'N/A')}")
        print(f"State: {state['flow_status']}")
        print(f"Next: {state['next_step']}")
        print(f"Task Issue: #{state['task_issue_number']}" if state['task_issue_number'] else "Task Issue: N/A")
        
        # Get and display linked issues
        links = self.store.get_issue_links(branch)
        if links:
            links_str = ", ".join([f"#{l['issue_number']} ({l['issue_role']})" for l in links])
            print(f"Linked Issues: {links_str}")
        else:
            print("Linked Issues: N/A")

        print(f"Spec Ref: {state['spec_ref']}")
        print(f"Branch: {state['branch']}")
        print(f"PR: {state['pr_number']}" if state['pr_number'] else "PR: N/A")


    def status(self):
        if self.json_output:
            # Get all flows from DB
            import sqlite3
            flows = []
            with sqlite3.connect(self.store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM flow_state")
                for row in cursor.fetchall():
                    flows.append({
                        'flow_slug': row['flow_slug'],
                        'flow_status': row['flow_status'],
                        'task_issue_number': row['task_issue_number'],
                        'branch': row['branch']
                    })
            print(json.dumps({'flows': flows}, indent=2))
        else:
            print(f"{'FLOW':<25} {'STATE':<10} {'TASK':<10} {'BRANCH':<30}")
            print("-" * 75)

            # Get all flows from DB
            import sqlite3
            with sqlite3.connect(self.store.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM flow_state")
                for row in cursor.fetchall():
                    task = f"#{row['task_issue_number']}" if row['task_issue_number'] else "N/A"
                    print(f"{row['flow_slug']:<25} {row['flow_status']:<10} {task:<10} {row['branch']:<30}")

    def switch(self, name):
        # Translate slug to branch if needed
        branch_name = name if name.startswith("task/") else f"task/{name}"
        
        current_branch = self._get_current_branch()
        if current_branch == branch_name:
            print(f"Already on flow {name} ({branch_name})")
            return

        # 1. Stash current changes
        print(f"Stashing changes on {current_branch}...")
        try:
            # We use a specific message to easily find it later if needed
            subprocess.check_call(['git', 'stash', 'push', '-m', f'vibe3-flow-auto-stash-{current_branch}'])
        except subprocess.CalledProcessError:
            print("No changes to stash or stash failed.")

        # 2. Checkout target
        print(f"Switching to {branch_name}...")
        try:
            subprocess.check_call(['git', 'checkout', branch_name])
        except subprocess.CalledProcessError:
            print(f"Error: Could not switch to {branch_name}")
            return

        # 3. Restore stash if exists
        # This is tricky because we don't know if the top stash is the one for this branch
        # But per-flow stash management is better
        # For now, we'll try to find a stash with the matching message
        stashes = subprocess.check_output(['git', 'stash', 'list']).decode().splitlines()
        for i, line in enumerate(stashes):
            if f'vibe3-flow-auto-stash-{branch_name}' in line:
                print(f"Restoring stash for {branch_name}...")
                subprocess.check_call(['git', 'stash', 'pop', f'stash@{{{i}}}'])
                break
        
        print(f"Switched to flow {name} ({branch_name})")

    def new(self, name, bind_issue=None):
        # 1. Create branch if it doesn't exist
        # For simplicity in this dev stage, we'll prefix with task/ if not present
        branch_name = name if name.startswith("task/") else f"task/{name}"
        
        try:
            subprocess.check_call(['git', 'rev-parse', '--verify', branch_name], stderr=subprocess.DEVNULL)
            print(f"Branch {branch_name} already exists. Switching...")
            subprocess.check_call(['git', 'checkout', branch_name])
        except subprocess.CalledProcessError:
            print(f"Creating new branch {branch_name}...")
            subprocess.check_call(['git', 'checkout', '-b', branch_name])

        # 2. Register in DB
        self.store.update_flow_state(branch_name, flow_slug=name)
        
        if bind_issue:
            self.bind_task(bind_issue, branch_name)
        
        print(f"Flow '{name}' initialized on branch {branch_name}")

    def bind_task(self, issue_number, branch=None):
        if not branch:
            branch = self._get_current_branch()
        
        self.store.update_flow_state(branch, task_issue_number=issue_number)
        self.store.add_issue_link(branch, issue_number, 'task')
        print(f"Bound task issue #{issue_number} as primary anchor to flow on branch {branch}")

    def bind_issue(self, issue_number, branch=None):
        if not branch:
            branch = self._get_current_branch()
        
        self.store.add_issue_link(branch, issue_number, 'link')
        print(f"Linked repo issue #{issue_number} to flow on branch {branch}")

