## 1. Refactor Flow and Task Resolution

- [x] 1.1 Refactor `lib/flow_runtime.sh` to remove `git rev-parse --show-toplevel` and path/worktree matching logic, relying solely on branch.
- [x] 1.2 Update `lib/task_query.sh` to remove reverse lookups using the current directory path against `worktrees.json`.
- [x] 1.3 Refactor `lib/check_pr_status.sh` to read branch bindings directly instead of checking `assigned_worktree` and `worktrees.json`.

## 2. Clean Up Audit and Verification Scripts

- [x] 2.1 Remove legacy worktree/branch repair logic from `lib/task_audit.sh` and `lib/task_audit_branches.sh`.
- [x] 2.2 Update `lib/task_actions.sh` remove/bind actions to no longer check `worktrees.json` for validation.

## 3. Update Documentation

- [x] 3.1 Revise `docs/standards/command-standard.md` (around line 69) to clarify that vibe flow uses branch, not `worktrees.json`, to express open site containers.
