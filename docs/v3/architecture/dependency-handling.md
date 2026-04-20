# Dependency Handling Mechanism

## Overview

Vibe Center 3.0 支持声明式依赖管理：当一个 flow 依赖其他 issue 时，系统会自动：

1. 将依赖方 flow 标记为 `waiting` 直到所有依赖满足
2. 在依赖完成（PR 创建）后自动唤醒依赖方
3. 从依赖的 PR 分支创建依赖方的开发分支，确保代码基于依赖的最新版本

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Orchestra Dispatcher (collect_ready_issues)                      │
│  - Check dependencies before scheduling                           │
│  - Mark flow as waiting if any dependency unsatisfied             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  PR Service                                                      │
│  - After PR creation, trigger DependencySatisfied event          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Event Bus (Domain Event)                                        │
│  - DependencySatisfied event published                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Dependency Wake-up Handler                                       │
│  - Find all flows waiting on this dependency issue               │
│  - Check if ALL dependencies are satisfied                       │
│  - Wake up flow: waiting → active, clear blocked fields          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Worktree Manager                                                │
│  - When creating worktree for woken-up flow                      │
│  - Fetch PR head branch from dependency                           │
│  - Create worktree from PR branch instead of origin/main         │
│  - Fallback to origin/main if PR fetch fails                      │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Dependency Checking in Dispatcher

**Location**: `src/vibe3/orchestra/services/state_label_dispatch.py`

**Methods**:
- `_get_issue_dependencies(issue_number)` - Get all dependency issue numbers from `flow_issue_links`
- `_is_dependency_satisfied(dep_issue_number)` - Check if dependency is satisfied:
  - Issue closed → satisfied
  - Issue has `state/done` or `state/merged` label → satisfied
  - Issue body mentions "pull request" or "pr #" → satisfied
  - Otherwise → not satisfied
- `_mark_issue_waiting(issue_number, unresolved_deps)` - Mark flow as waiting:
  - Set `flow_status = "waiting"`
  - Set `blocked_by_issue` to first unresolved dependency
  - Add `dependency_waiting` event to flow history

**Integration**: `collect_ready_issues()` checks dependencies before including issue in ready list.

### 2. Auto Wake-up Mechanism

**Event Definition**: `src/vibe3/domain/events/flow_lifecycle.py` - `DependencySatisfied`

**Trigger**: `src/vibe3/services/pr_service.py` - After successful PR creation, `_trigger_dependency_wake_up()` publishes the event.

**Handler**: `src/vibe3/domain/handlers/dependency_wake_up.py`

**Handler Steps**:
1. `_find_waiting_flows(store, dep_issue_number)` - Query `flow_state` for flows where `flow_status = 'waiting' AND blocked_by_issue = dep_issue_number`
2. For each waiting flow:
   - `_get_all_dependencies(store, branch)` - Get all dependency issue numbers
   - Check **all** dependencies are satisfied
   - If all satisfied: `_wake_up_flow()`:
     - Set `flow_status = "active"`
     - Clear `blocked_by_issue` and `blocked_reason`
     - Add `dependency_wake_up` event with `source_pr` reference
     - Update GitHub labels (remove `state/blocked`, add `state/ready`)

### 3. Branch Creation from PR Source

**Location**: `src/vibe3/environment/worktree.py`

**Logic**: When creating a new worktree for an issue:
1. Check flow history for `dependency_wake_up` event
2. If found, get `source_pr` from most recent wake-up event
3. Fetch PR info from GitHub to get `head_branch`
4. Fetch the PR branch from origin
5. If fetch successful: create worktree from `origin/<head_branch>` with `-b <new-branch>`
6. If fetch fails: log warning, record `dependency_branch_fallback` event, fall back to `origin/main`

**Benefits**:
- Dependent flow always starts from the latest code of the dependency
- Avoids merge conflicts when dependency hasn't been merged yet
- Maintains correct dependency hierarchy in code

## Data Model

### Tables

- `flow_state`: Added `flow_status = 'waiting'` option, uses existing `blocked_by_issue` field
- `flow_issue_links`: Existing table, `issue_role = 'dependency'` stores dependency relationships
- `flow_events`: Existing table, events:
  - `dependency_waiting` - flow marked as waiting
  - `dependency_wake_up` - flow woken up when all dependencies satisfied
  - `dependency_branch_fallback` - fallback to main when PR fetch fails

### Status Semantics

| Status  | Meaning                                    | Recovery                          |
|---------|--------------------------------------------|-----------------------------------|
| `active`| Ready for execution                        | N/A                               |
| `waiting`| Waiting for dependencies to be satisfied  | Auto recovery when all dependencies done |
| `blocked`| Internal execution error                   | Manual recovery required           |
| `failed` | Execution failed                           | Manual recovery required           |

## Usage

### Declaring Dependencies

Add dependency relationship via `flow_issue_links`:

```sql
INSERT INTO flow_issue_links (branch, issue_number, issue_role)
VALUES ('task/issue-100', 100, 'task');
INSERT INTO flow_issue_links (branch, issue-100', 99, 'dependency');
```

When orchestra collects ready issues:
- Issue 100 will be marked `waiting` until issue 99 has PR created
- After issue 99 creates PR → issue 100 automatically woken up

## Fallback Behavior

- **PR fetch fails**: Network error, PR branch deleted, permission error → fall back to `origin/main`, log event
- **Partial dependencies satisfied**: Flow stays `waiting` until all dependencies done
- **Multiple dependencies**: Only wake up when **all** dependencies are satisfied

## Backward Compatibility

- No database schema changes: uses existing tables and fields
- Existing flows with `active/blocked/failed/done` are unaffected
- Only flows with explicit dependency relationships get the new behavior
- Disabled for flows without dependencies - behaves exactly as before

## Future Enhancements

Possible future extensions (not implemented in this phase):

1. **Cycle detection**: Detect circular dependencies before execution starts
2. **Dependency failure handling**: If dependency PR is closed without merge, automatically block dependent flow
3. **CI wait option**: Optionally wait for CI pass before waking up dependent flow
4. **Priority ordering**: Wake up dependent flows in dependency order
