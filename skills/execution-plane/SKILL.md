---
name: execution-plane
description: V3 Execution Plane - Worktree/Tmux session orchestration and recovery
category: process
trigger: auto
enforcement: advisory
phase: convergence
---

# Execution Plane Skill

## System Role

You are the Execution Plane skill for Vibe Center V3 architecture. You manage:
- Worktree creation, validation, and cleanup
- Tmux session creation, attachment, and recovery
- Execution result persistence and querying
- Session recovery for interrupted work

You enforce naming conventions and maintain execution contracts.

## Overview

The Execution Plane handles all worktree and tmux operations for multi-agent parallel development. It provides standardized interfaces for both human users and OpenClaw automated agents.

## When to Use

- Creating new worktrees with standardized naming
- Managing tmux sessions for parallel development
- Recovering work sessions after interruption
- Querying execution state across worktrees
- Validating worktree integrity

## Execution Steps

### 1. Worktree Operations

```bash
# Create worktree with auto-naming
wtnew <task-slug> [agent=claude] [base=main]

# List worktrees with filtering
wtlist [owner] [task]

# Validate worktree
wtvalidate [worktree-name]

# Cleanup worktree with confirmation
wtrm <worktree-name> [--force]
```

### 2. Tmux Session Operations

```bash
# Create session with auto-naming
tmnew <task-slug> [agent=claude]

# Attach to session (auto-detect from worktree)
tmattach [session]

# List sessions with task context
tmlist

# Switch between sessions
tmswitch <session>

# Kill session with confirmation
tmkill <session> [--force]

# Rename session
tmrename <old-name> <new-name>
```

### 3. Session Recovery

```bash
# Recover by task_id
wtrecover --task-id <task-id>

# Recover by worktree
wtrecover --worktree <worktree-path>

# Recover by session
wtrecover --session <session-name>

# View recovery history
wtrecover-history [task-id]
```

### 4. Execution Contract Operations

```bash
# Write execution result (usually called by wtnew/tmnew)
write_execution_result <task_id> <worktree> <session>

# Query execution results
query_by_task_id <task-id>
query_by_worktree <worktree>
query_by_session <session>

# Update execution result
update_execution_result <task_id> <field> <value>

# Cleanup old results
cleanup_execution_results
```

## Naming Conventions

### Worktree Names
- Format: `wt-<owner>-<task-slug>`
- Example: `wt-claude-add-user-auth`
- Conflict handling: Auto-append 4-char suffix (e.g., `wt-claude-add-user-auth-a1b2`)

### Tmux Session Names
- Format: `<agent>-<task-slug>`
- Example: `claude-add-user-auth`
- Must match worktree naming (minus `wt-` prefix)

## Execution Modes

### Human Mode (Default)
```bash
wtnew add-user-auth
# Sets executor="human" in execution result
```

### OpenClaw Mode
```bash
EXECUTOR=openclaw wtnew add-user-auth
# Sets executor="openclaw" in execution result
```

## Output Format

### Worktree Creation
```
✅ Created worktree: wt-claude-add-user-auth -> add-user-auth (base: main)
👤 Identity: Agent-Claude <agent-claude@vibecoding.ai>
✓ Execution result written: .agent/execution-results/add-user-auth.json
```

### Session Recovery
```
🔍 Recovering session...
  Task ID: add-user-auth
  Worktree: wt-claude-add-user-auth
  Session: claude-add-user-auth
✓ Switching to worktree: wt-claude-add-user-auth
✓ Session found: claude-add-user-auth
✓ Attaching to session...

✅ Recovery complete (2s)
```

### Validation Output
```
🔍 Validating worktree: wt-claude-add-user-auth
--------------------------------
✓ Checking naming convention...
  ✅ Naming valid
✓ Checking git status...
  Branch: add-user-auth
  Tracking: origin/add-user-auth
  ✅ Working directory clean
  ✅ Git repository integrity OK
--------------------------------
✅ Validation complete
```

## What This Skill Does NOT Do

- Does NOT manage task lifecycle (handled by Control Plane)
- Does NOT implement provider routing (handled by Process Plane)
- Does NOT create complex caching systems (keeps it simple with JSON files)
- Does NOT override CLAUDE.md HARD RULES (enforces LOC limits, naming conventions)
- Does NOT implement custom test frameworks (uses existing bats)

## Error Handling

### Naming Validation Errors
- Invalid format: Shows expected format and examples
- Conflict detection: Auto-generates suffix or prompts user

### Recovery Errors
- Worktree missing: Reports error with manual recovery steps
- Session lost: Recreates session automatically
- Execution result missing: Suggests alternative recovery methods

### Git Errors
- Not on main branch: Prompts to switch first
- Worktree corruption: Reports validation failure with repair steps

## Integration Points

### Control Plane Integration
- Reads execution intent: `task_id`, `worktree_hint`, `session_hint`
- Writes execution results: `resolved_worktree`, `resolved_session`, `executor`, `timestamp`

### Process Plane Integration
- Can be called by OpenClaw with `EXECUTOR=openclaw`
- Returns structured JSON for automated parsing

### Worktree Aliases
- Sources `config/aliases/worktree.sh` for core operations
- Sources `config/aliases/tmux.sh` for session management
- Sources `config/aliases/execution-contract.sh` for persistence

## Performance Targets

- Session recovery: < 30 seconds
- Naming conflict rate: < 0.1% for 5+ parallel sessions
- Execution result query: < 1 second
- Worktree validation: < 5 seconds

## Troubleshooting

### Worktree Name Already Exists
```bash
# Solution 1: Let auto-suffix handle it
wtnew add-user-auth  # Creates wt-claude-add-user-auth-a1b2

# Solution 2: Remove old worktree first
wtrm wt-claude-add-user-auth --force
wtnew add-user-auth
```

### Session Lost After Restart
```bash
# Recovery command recreates session automatically
wtrecover --task-id add-user-auth
```

### Execution Result Corruption
```bash
# Backup and rebuild
cleanup_execution_results
# Then recreate worktree/session
wtnew add-user-auth
```

## Examples

### Full Workflow: Human Mode
```bash
# 1. Create worktree
wtnew add-user-auth claude main

# 2. Create tmux session
tmnew add-user-auth claude

# 3. Work in session...
# (development happens)

# 4. Validate worktree
wtvalidate wt-claude-add-user-auth

# 5. Cleanup when done
wtrm wt-claude-add-user-auth
tmkill claude-add-user-auth
```

### Full Workflow: OpenClaw Mode
```bash
# 1. Set executor mode
export EXECUTOR=openclaw

# 2. Create worktree (writes execution result)
wtnew implement-api codex main

# 3. Create session
tmnew implement-api codex

# 4. Query state
query_by_task_id implement-api

# 5. Cleanup
EXECUTOR=openclaw wtrm wt-codex-implement-api --force
```

### Recovery Scenario
```bash
# Lost session after system restart
wtrecover --worktree wt-claude-add-user-auth

# Or by task_id
wtrecover --task-id add-user-auth

# Check recovery history
wtrecover-history add-user-auth
```
