from lib.store import Vibe3Store
from lib.github import GitHubHelper
import subprocess
import json

class TaskManager:
    def __init__(self, json_output=False, auto_confirm=False):
        self.store = Vibe3Store()
        self.json_output = json_output
        self.auto_confirm = auto_confirm

    def _get_current_branch(self):
        return subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']).decode().strip()

    def add_from_repo_issue(self, issue_number, group=None, agent=None):
        branch = self._get_current_branch()
        
        # update_flow_state stores the primary task issue for the flow
        self.store.update_flow_state(branch, task_issue_number=issue_number, executor_actor=agent)
        
        # Add record to flow_issue_links with role='task'
        self.store.add_issue_link(branch, issue_number, 'task')
        
        print(f"Added task issue #{issue_number} as primary anchor for flow on branch {branch}")
        if group:
            print(f"Task group set to: {group}")
        if agent:
            print(f"Task agent set to: {agent}")

    def list(self):
        issues = GitHubHelper.list_issues()
        if not issues:
            print("No issues found or error fetching issues.")
            return

        # Get all issue links from active flows to show status
        active_flows = self.store.get_active_flows()
        linked_issues = {} # issue_number -> branch
        for flow in active_flows:
            # Add primary task issue
            if flow.get('task_issue_number'):
                linked_issues[flow['task_issue_number']] = flow['branch']
            
            # Add other linked issues
            links = self.store.get_issue_links(flow['branch'])
            for link in links:
                linked_issues[link['issue_number']] = flow['branch']


        print(f"{'ID':<10} {'Title':<50} {'Status':<10} {'Flow/Branch'}")
        print("-" * 100)
        for issue in issues:
            num = issue['number']
            title = (issue['title'][:47] + '...') if len(issue['title']) > 50 else issue['title']
            state = issue['state']
            flow_branch = linked_issues.get(num, "N/A")
            print(f"#{num:<9} {title:<50} {state:<10} {flow_branch}")

    def show(self, issue_number=None):
        if issue_number is None:
            # Try to get task issue from current branch
            branch = self._get_current_branch()
            state = self.store.get_flow_state(branch)
            if state and state.get('task_issue_number'):
                issue_number = state['task_issue_number']
            else:
                print("Error: No task issue number provided and current branch has no bound task.")
                return

        issue = GitHubHelper.view_issue(issue_number)
        if not issue:
            print(f"Failed to fetch issue #{issue_number}")
            return

        print(f"Task: #{issue['number']} - {issue['title']}")
        print(f"State: {issue['state']}")
        print("-" * 40)
        
        # Show local handoff info
        branch = self._get_current_branch()
        state = self.store.get_flow_state(branch)
        if state and state.get('task_issue_number') == int(issue_number):
            print("Local Handoff State:")
            print(f"  Branch: {state['branch']}")
            print(f"  Plan: {state.get('plan_ref', 'N/A')}")
            print(f"  Next Step: {state.get('next_step', 'N/A')}")
            print(f"  Blocked By: {state.get('blocked_by', 'N/A')}")
        else:
            print("No local handoff state for this issue on current branch.")

    def link_repo_issue(self, issue_number):
        branch = self._get_current_branch()
        self.store.add_issue_link(branch, issue_number, 'link')
        print(f"Linked repo issue #{issue_number} to current flow branch {branch}.")

