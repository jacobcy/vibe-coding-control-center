# Execution Plane Skill - Usage Guide

## Quick Start

### For Human Users

```bash
# 1. Create a new worktree for a task
wtnew add-user-auth claude main

# 2. Create a tmux session
tmnew add-user-auth claude

# 3. Work in the session...
# (development happens)

# 4. Validate your worktree
wtvalidate wt-claude-add-user-auth

# 5. When done, clean up
wtrm wt-claude-add-user-auth
tmkill claude-add-user-auth
```

### For OpenClaw Agents

```bash
# 1. Prepare complete environment
skill_prepare_environment implement-api openclaw main

# 2. Query execution state
skill_query_task implement-api

# 3. When done, cleanup
skill_cleanup_environment implement-api openclaw
```

## Common Workflows

### Workflow 1: Starting a New Task

```bash
# Create worktree and session in one go
wtnew fix-login-bug claude main
tmnew fix-login-bug claude

# Verify creation
wtlist claude fix-login-bug
tmlist | grep fix-login-bug
```

### Workflow 2: Recovering a Lost Session

```bash
# System restarted, session lost
wtrecover --task-id add-user-auth

# Or recover by worktree
wtrecover --worktree wt-claude-add-user-auth

# Check recovery history
wtrecover-history add-user-auth
```

### Workflow 3: Managing Multiple Parallel Tasks

```bash
# List all worktrees for a specific agent
wtlist claude

# List all sessions
tmlist

# Switch between sessions
tmswitch claude-add-user-auth
tmswitch claude-fix-login-bug

# Clean up multiple worktrees
wtrm all  # Removes all wt-* worktrees with confirmation
```

### Workflow 4: Validation and Debugging

```bash
# Validate worktree integrity
wtvalidate wt-claude-add-user-auth

# Check execution result
query_by_task_id add-user-auth

# Check naming conflicts
wtlist | grep add-user-auth
```

## Naming Conventions

### Worktree Names
- **Format**: `wt-<owner>-<task-slug>`
- **Examples**:
  - `wt-claude-add-user-auth`
  - `wt-opencode-implement-api`
  - `wt-codex-fix-bug-123`
- **Conflict handling**: Auto-appends 4-char suffix (e.g., `-a1b2`)

### Tmux Session Names
- **Format**: `<agent>-<task-slug>`
- **Examples**:
  - `claude-add-user-auth`
  - `opencode-implement-api`
  - `codex-fix-bug-123`
- **Must match worktree** (minus `wt-` prefix)

## Command Reference

### Worktree Commands

| Command | Description | Example |
|---------|-------------|---------|
| `wtnew` | Create new worktree | `wtnew add-auth claude main` |
| `wtlist` | List worktrees (with filters) | `wtlist claude auth` |
| `wtvalidate` | Validate worktree integrity | `wtvalidate wt-claude-auth` |
| `wtrm` | Remove worktree | `wtrm wt-claude-auth` |
| `wt` | Jump to worktree | `wt wt-claude-auth` |

### Tmux Commands

| Command | Description | Example |
|---------|-------------|---------|
| `tmnew` | Create new session | `tmnew add-auth claude` |
| `tmattach` | Attach to session | `tmattach claude-auth` |
| `tmlist` | List sessions | `tmlist` |
| `tmswitch` | Switch session | `tmswitch claude-auth` |
| `tmkill` | Kill session | `tmkill claude-auth` |
| `tmrename` | Rename session | `tmrename old new` |

### Recovery Commands

| Command | Description | Example |
|---------|-------------|---------|
| `wtrecover --task-id` | Recover by task ID | `wtrecover --task-id add-auth` |
| `wtrecover --worktree` | Recover by worktree | `wtrecover --worktree wt-claude-auth` |
| `wtrecover --session` | Recover by session | `wtrecover --session claude-auth` |
| `wtrecover-history` | View recovery history | `wtrecover-history add-auth` |

### Skill Wrapper Commands (OpenClaw)

| Command | Description | Example |
|---------|-------------|---------|
| `skill_wtnew` | Create worktree (OpenClaw mode) | `skill_wtnew task openclaw` |
| `skill_tmnew` | Create session (OpenClaw mode) | `skill_tmnew task openclaw` |
| `skill_wtrecover` | Recover session (OpenClaw mode) | `skill_wtrecover task-id add-auth` |
| `skill_prepare_environment` | Create complete environment | `skill_prepare_environment task openclaw` |
| `skill_cleanup_environment` | Remove complete environment | `skill_cleanup_environment task openclaw` |

## Troubleshooting

### Issue: Worktree name already exists

**Symptom**: `⚠️ Naming conflict detected`

**Solution**:
```bash
# Option 1: Let auto-suffix handle it
wtnew add-user-auth  # Creates wt-claude-add-user-auth-a1b2

# Option 2: Remove old worktree first
wtrm wt-claude-add-user-auth --force
wtnew add-user-auth
```

### Issue: Session lost after restart

**Symptom**: `❌ Session not found: claude-auth`

**Solution**:
```bash
# Recovery command recreates session automatically
wtrecover --task-id add-user-auth

# Or recreate manually
tmnew add-user-auth claude
```

### Issue: Execution result corrupted

**Symptom**: `✗ Failed to validate execution result`

**Solution**:
```bash
# Backup and rebuild
cleanup_execution_results

# Then recreate worktree/session
wtnew add-user-auth claude main
tmnew add-user-auth claude
```

### Issue: Not on main branch

**Symptom**: `⚠️ On 'feature-branch', not main`

**Solution**:
```bash
# Switch to main first
cd $(git rev-parse --show-toplevel)
git checkout main

# Then create worktree
wtnew add-user-auth
```

### Issue: Worktree validation fails

**Symptom**: `❌ Git repository corruption detected`

**Solution**:
```bash
# Check git integrity
git fsck --full

# If corruption detected, remove and recreate
wtrm wt-claude-add-user-auth --force
wtnew add-user-auth
```

## Advanced Usage

### Querying Execution State

```bash
# Query by task_id
query_by_task_id add-user-auth

# Query by worktree
query_by_worktree wt-claude-add-user-auth

# Query by session
query_by_session claude-add-user-auth

# Results are JSON format for easy parsing
query_by_task_id add-user-auth | jq '.resolved_worktree'
```

### Batch Operations

```bash
# Remove all worktrees for an agent
wtlist claude | grep wt-claude | xargs -I {} wtrm {} --force

# Kill all sessions for an agent
tmlist | grep claude- | cut -d' ' -f1 | xargs -I {} tmkill {} --force

# Validate all worktrees
wtlist | grep wt- | cut -d' ' -f1 | xargs -I {} wtvalidate {}
```

### Integration with CI/CD

```bash
# In CI pipeline
export EXECUTOR=openclaw

# Prepare environment
skill_prepare_environment ci-test openclaw main

# Run tests
cd wt-openclaw-ci-test
./run-tests.sh

# Cleanup
cd ..
skill_cleanup_environment ci-test openclaw
```

## Performance Tips

1. **Use auto-detection**: `tmattach` without arguments auto-detects session from current worktree
2. **Batch cleanup**: Use `wtrm all` to clean up multiple worktrees at once
3. **Recovery history**: Check `wtrecover-history` to understand recovery patterns
4. **Validation**: Run `wtvalidate` before critical operations to ensure integrity

## Best Practices

1. **Always use standardized naming**: Ensures consistency and enables auto-recovery
2. **Clean up when done**: Remove worktrees and sessions after task completion
3. **Validate regularly**: Run `wtvalidate` periodically to catch issues early
4. **Use recovery commands**: Don't manually recreate sessions; use `wtrecover`
5. **Check execution results**: Use query commands to verify state before operations

## Getting Help

- **Skill documentation**: `skills/execution-plane/SKILL.md`
- **Troubleshooting**: See above troubleshooting section
- **Validation errors**: Run `wtvalidate` for detailed diagnostics
- **Recovery issues**: Check `wtrecover-history` for patterns
