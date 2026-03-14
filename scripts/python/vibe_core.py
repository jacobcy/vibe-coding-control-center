#!/usr/bin/env python3
"""
Vibe 3.0 Python Core
This script is the main logic hub for Vibe 3.0.
"""

import sys
import os
import json
import argparse

# Add current directory to path for local imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flow.manager import FlowManager


def get_version():
    return "3.0.0-dev"

def handle_flow(subcommand, args_list, json_output=False, auto_confirm=False):
    # Nested parser for flow subcommands
    parser = argparse.ArgumentParser(prog="vibe3 flow")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("-y", "--yes", action="store_true", dest="auto_confirm",
                        help="Auto-confirm prompts")

    subparsers = parser.add_subparsers(dest="sub")

    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("name")
    new_parser.add_argument("--bind", help="Bind to repo issue")

    switch_parser = subparsers.add_parser("switch")
    switch_parser.add_argument("name")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("branch", nargs="?")

    status_parser = subparsers.add_parser("status")

    bind_parser = subparsers.add_parser("bind")
    bind_parser.add_argument("--issue", type=int, help="Bind a repo issue")
    bind_subparsers = bind_parser.add_subparsers(dest="bind_sub")
    task_bind_parser = bind_subparsers.add_parser("task")
    task_bind_parser.add_argument("number", type=int)

    freeze_parser = subparsers.add_parser("freeze")
    freeze_parser.add_argument("--by", required=True, help="Reason for freezing")

    # Parse with global flags allowed at subcommand level
    parsed, _ = parser.parse_known_args([subcommand] + args_list if subcommand else args_list)

    # Merge global and subcommand-level flags
    final_json = json_output or getattr(parsed, 'json', False)
    final_auto = auto_confirm or getattr(parsed, 'auto_confirm', False)

    manager = FlowManager(json_output=final_json, auto_confirm=final_auto)

    if subcommand == "new":
        manager.new(parsed.name, parsed.bind)
    elif subcommand == "switch":
        manager.switch(parsed.name)
    elif subcommand == "show":
        manager.show(parsed.branch)
    elif subcommand == "status":
        manager.status()
    elif subcommand == "bind":
        if parsed.issue:
            manager.bind_issue(parsed.issue)
        elif parsed.bind_sub == "task":
            manager.bind_task(parsed.number)
        else:
            print("Error: Specify --issue <num> or task <num>")
    elif subcommand == "freeze":
        manager.freeze(parsed.by)
    else:
        print(f"Flow subcommand '{subcommand}' not yet implemented in 3.0.")



from task.manager import TaskManager

def handle_task(subcommand, args_list, json_output=False, auto_confirm=False):
    parser = argparse.ArgumentParser(prog="vibe3 task")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("-y", "--yes", action="store_true", dest="auto_confirm",
                        help="Auto-confirm prompts")

    subparsers = parser.add_subparsers(dest="sub")

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--repo-issue", type=int, required=True)

    list_parser = subparsers.add_parser("list")

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("number", nargs="?", type=int)
    
    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("number", nargs="?", type=int)
    update_parser.add_argument("--status", choices=["active", "completed", "blocked", "idle"])
    update_parser.add_argument("--next-step", help="Update next step")
    update_parser.add_argument("--blocked-by", help="Mark as blocked by something")

    link_parser = subparsers.add_parser("link")
    link_parser.add_argument("--repo-issue", type=int, required=True)

    # Parse with global flags allowed at subcommand level
    parsed, _ = parser.parse_known_args([subcommand] + args_list if subcommand else args_list)

    # Merge global and subcommand-level flags
    final_json = json_output or getattr(parsed, 'json', False)
    final_auto = auto_confirm or getattr(parsed, 'auto_confirm', False)

    manager = TaskManager(json_output=final_json, auto_confirm=final_auto)

    if subcommand == "add":
        if parsed.repo_issue:
            manager.add_from_repo_issue(parsed.repo_issue, getattr(parsed, 'group', None), getattr(parsed, 'agent', None))
        else:
            print("Error: --repo-issue is required for task add in 3.0.")
    elif subcommand == "list":
        manager.list()
    elif subcommand == "show":
        manager.show(parsed.number)
    elif subcommand == "update":
        manager.update(parsed.number, status=parsed.status, next_step=parsed.next_step, blocked_by=parsed.blocked_by)
    elif subcommand == "link":
        manager.link_repo_issue(parsed.repo_issue)
    else:
        print(f"Task subcommand '{subcommand}' not yet implemented in 3.0.")


from pr.manager import PRManager

def handle_pr(subcommand, args_list, json_output=False, auto_confirm=False):
    parser = argparse.ArgumentParser(prog="vibe3 pr")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("-y", "--yes", action="store_true", dest="auto_confirm",
                        help="Auto-confirm prompts")

    subparsers = parser.add_subparsers(dest="sub")

    draft_parser = subparsers.add_parser("draft")
    draft_parser.add_argument("--title")
    draft_parser.add_argument("--body")

    show_parser = subparsers.add_parser("show")

    ready_parser = subparsers.add_parser("ready")

    merge_parser = subparsers.add_parser("merge")

    # Parse with global flags allowed at subcommand level
    parsed, _ = parser.parse_known_args([subcommand] + args_list if subcommand else args_list)

    # Merge global and subcommand-level flags
    final_json = json_output or getattr(parsed, 'json', False)
    final_auto = auto_confirm or getattr(parsed, 'auto_confirm', False)

    manager = PRManager(json_output=final_json, auto_confirm=final_auto)

    if subcommand == "draft":
        manager.draft(parsed.title, parsed.body)
    elif subcommand == "show":
        manager.show()
    elif subcommand == "ready":
        manager.ready()
    elif subcommand == "merge":
        manager.merge()
    else:
        print(f"PR subcommand '{subcommand}' not yet implemented in 3.0.")


from handoff.manager import HandoffManager
from audit.manager import AuditManager

def handle_handoff(subcommand, args_list, json_output=False, auto_confirm=False):
    parser = argparse.ArgumentParser(prog="vibe3 handoff")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("-y", "--yes", action="store_true", dest="auto_confirm",
                        help="Auto-confirm prompts")

    subparsers = parser.add_subparsers(dest="sub")

    # plan, report, audit read-only
    subparsers.add_parser("plan")
    subparsers.add_parser("report")
    subparsers.add_parser("audit")

    # auth
    auth_parser = subparsers.add_parser("auth")
    auth_parser.add_argument("role", choices=["plan", "report", "audit"])
    auth_parser.add_argument("--agent")
    auth_parser.add_argument("--model")

    # edit
    edit_parser = subparsers.add_parser("edit")
    edit_parser.add_argument("type", choices=["plan", "report", "audit"])

    # sync
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("type", choices=["plan", "report", "audit"], nargs="?")

    # Parse with global flags
    parsed, _ = parser.parse_known_args([subcommand] + args_list if subcommand else args_list)

    final_json = json_output or getattr(parsed, 'json', False)
    final_auto = auto_confirm or getattr(parsed, 'auto_confirm', False)

    manager = HandoffManager(json_output=final_json, auto_confirm=final_auto)

    if subcommand in ["plan", "report", "audit"]:
        manager.show(subcommand)
    elif subcommand == "auth":
        manager.auth(parsed.role, parsed.agent, parsed.model)
    elif subcommand == "edit":
        manager.edit(parsed.type)
    elif subcommand == "sync":
        manager.sync(parsed.type)
    else:
        print(f"Handoff subcommand '{subcommand}' not yet implemented.")

def handle_check(json_output=False):
    manager = AuditManager(json_output=json_output)
    manager.check()

def main():
    parser = argparse.ArgumentParser(description="Vibe 3.0 Python Core")
    parser.add_argument("--version", action="store_true", help="Show version")

    subparsers = parser.add_subparsers(dest="command", help="V3 Commands")

    # Flow
    flow_parser = subparsers.add_parser("flow", help="Manage flows")
    flow_parser.add_argument("subcommand", nargs="?", help="Subcommand (new, bind, etc.)")
    flow_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    flow_parser.add_argument("-y", "--yes", action="store_true", dest="auto_confirm",
                              help="Auto-confirm prompts")

    # Task
    task_parser = subparsers.add_parser("task", help="Manage tasks")
    task_parser.add_argument("subcommand", nargs="?", help="Subcommand (add, show, etc.)")
    task_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    task_parser.add_argument("-y", "--yes", action="store_true", dest="auto_confirm",
                              help="Auto-confirm prompts")

    # PR
    pr_parser = subparsers.add_parser("pr", help="Manage PRs")
    pr_parser.add_argument("subcommand", nargs="?", help="Subcommand (draft, ready, etc.)")
    pr_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    pr_parser.add_argument("-y", "--yes", action="store_true", dest="auto_confirm",
                              help="Auto-confirm prompts")

    # Handoff
    handoff_parser = subparsers.add_parser("handoff", help="Manage handoffs")
    handoff_parser.add_argument("subcommand", nargs="?", help="Subcommand (plan, report, audit, auth, edit)")
    handoff_parser.add_argument("--json", action="store_true", help="Output in JSON format")
    handoff_parser.add_argument("-y", "--yes", action="store_true", dest="auto_confirm",
                              help="Auto-confirm prompts")

    # Check
    check_parser = subparsers.add_parser("check", help="Run audit checks")
    check_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args, remaining = parser.parse_known_args()

    if args.version:
        print(f"Vibe Python Core {get_version()}")
        sys.exit(0)

    if args.command == "flow":
        json_out = getattr(args, 'json', False)
        auto_conf = getattr(args, 'auto_confirm', False)
        handle_flow(args.subcommand, remaining, json_output=json_out, auto_confirm=auto_conf)
    elif args.command == "task":
        json_out = getattr(args, 'json', False)
        auto_conf = getattr(args, 'auto_confirm', False)
        handle_task(args.subcommand, remaining, json_output=json_out, auto_confirm=auto_conf)
    elif args.command == "pr":
        json_out = getattr(args, 'json', False)
        auto_conf = getattr(args, 'auto_confirm', False)
        handle_pr(args.subcommand, remaining, json_output=json_out, auto_confirm=auto_conf)
    elif args.command == "handoff":
        json_out = getattr(args, 'json', False)
        auto_conf = getattr(args, 'auto_confirm', False)
        handle_handoff(args.subcommand, remaining, json_output=json_out, auto_confirm=auto_conf)
    elif args.command == "check":
        json_out = getattr(args, 'json', False)
        handle_check(json_output=json_out)
    else:
        # If no command, help is shown by argparse
        if not args.command:
            parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
