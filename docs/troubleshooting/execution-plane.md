# Execution Plane Troubleshooting Guide

## Common Issues

### Issue 1: Naming Conflicts

**Symptom**: 
```
⚠️ Naming conflict detected, auto-generated suffix: a1b2
```

**Cause**: Worktree or session with same name already exists.

**Solution**:
```bash
# Option 1: Accept auto-suffix
wtnew add-user-auth  # Creates wt-claude-add-user-auth-a1b2

# Option 2: Remove conflicting worktree first
wtrm wt-claude-add-user-auth --force
wtnew add-user-auth
```

### Issue 2: Session Lost After Restart

**Symptom**:
```
❌ Session not found: claude-add-user-auth
```

**Cause**: Tmux server restarted or session killed.

**Solution**:
```bash
# Use recovery command
wtrecover --task-id add-user-auth

# Or recreate manually
tmnew add-user-auth claude
```

### Issue 3: Execution Result Corruption

**Symptom**:
```
✗ Failed to validate execution result
Missing required field: executor
```

**Cause**: JSON file corrupted or incomplete.

**Solution**:
```bash
# Check JSON file
cat .agent/execution-results/add-user-auth.json

# Validate with jq
jq empty .agent/execution-results/add-user-auth.json

# Backup and rebuild
cleanup_execution_results
wtnew add-user-auth  # Recreates execution result
```

### Issue 4: Worktree Validation Fails

**Symptom**:
```
❌ Git repository corruption detected
```

**Cause**: Git repository integrity issues.

**Solution**:
```bash
# Run git fsck
git fsck --full

# If corruption detected
git gc --prune=now
git fsck --full

# If still failing, recreate worktree
wtrm wt-claude-add-user-auth --force
wtnew add-user-auth
```

### Issue 5: Recovery Takes Too Long

**Symptom**: Recovery takes > 30 seconds.

**Cause**: Large repository or slow filesystem.

**Solution**:
```bash
# Check repository size
du -sh .git

# Optimize git
git gc --aggressive

# Check filesystem performance
time ls -la wt-claude-*
```

### Issue 6: Cross-Worktree Access Fails

**Symptom**:
```
❌ Execution result not found
```

**Cause**: Execution results not accessible from current worktree.

**Solution**:
```bash
# Verify shared location
ls -la .agent/execution-results/

# Check from main repo
cd $(git rev-parse --show-toplevel)
ls -la .agent/execution-results/

# Ensure .git/shared/ symlink exists
ls -la .git/shared/
```

### Issue 7: OpenClaw Mode Not Set

**Symptom**: Executor shows "human" instead of "openclaw".

**Cause**: EXECUTOR environment variable not set.

**Solution**:
```bash
# Set explicitly
export EXECUTOR=openclaw

# Or use skill wrapper
skill_wtnew add-feature openclaw main

# Verify
echo $EXECUTOR
```

### Issue 8: Parallel Session Conflicts

**Symptom**: Multiple agents creating conflicting worktrees.

**Cause**: Race conditions in parallel creation.

**Solution**:
```bash
# V3 handles this automatically with suffix
# Verify conflict rate ≈ 0
wtlist | wc -l  # Should match expected count

# Check for auto-suffixes
wtlist | grep -- -
```

## Performance Issues

### Slow Creation (> 5s)

**Diagnosis**:
```bash
time wtnew test-feature
```

**Causes**:
1. Large repository
2. Slow network (fetching)
3. Filesystem issues

**Solutions**:
```bash
# Skip fetch
wtnew test-feature claude main --no-fetch

# Use local base
git checkout -b test-feature
wtnew test-feature claude test-feature

# Check filesystem
df -h .
```

### Slow Recovery (> 30s)

**Diagnosis**:
```bash
time wtrecover --task-id test-feature
```

**Causes**:
1. Large worktree
2. Session recreation overhead
3. Execution result query slow

**Solutions**:
```bash
# Optimize worktree
git gc

# Pre-create session
tmnew test-feature claude

# Check query performance
time query_by_task_id test-feature
```

## Error Messages

### "Not in a git repo"

**Meaning**: Current directory is not a git repository.

**Solution**:
```bash
cd /path/to/repo
wtnew add-feature
```

### "On 'feature-branch', not main"

**Meaning**: Must create worktrees from main branch.

**Solution**:
```bash
git checkout main
wtnew add-feature
```

### "Worktree not found"

**Meaning**: Specified worktree doesn't exist.

**Solution**:
```bash
# List available worktrees
wtlist

# Check path
ls -la wt-*
```

### "Session not found"

**Meaning**: Tmux session doesn't exist.

**Solution**:
```bash
# List sessions
tmlist

# Create session
tmnew add-feature claude

# Or recover
wtrecover --task-id add-feature
```

## Debugging

### Enable Verbose Mode

```bash
# Worktree commands
DEBUG=1 wtnew add-feature

# Recovery commands
VERBOSE=1 wtrecover --task-id add-feature

# Execution contract
TRACE=1 query_by_task_id add-feature
```

### Check Logs

```bash
# Recovery history
cat .agent/recovery-history.log

# Git worktree list
git worktree list --porcelain

# Tmux sessions
tmux list-sessions -F "#{session_name} #{?session_attached,*,}"
```

### Validate Environment

```bash
# Run full validation
wtvalidate wt-claude-add-feature

# Check execution results
find .agent/execution-results -name "*.json" -exec jq empty {} \;

# Test naming convention
_validate_worktree_name wt-claude-test
```

## Getting Help

1. **Documentation**: `skills/execution-plane/README.md`
2. **Rules**: `.agent/rules/execution-plane.md`
3. **Migration**: `docs/migration/v2-to-v3-execution-plane.md`
4. **Issues**: Create issue with:
   - Error message
   - Steps to reproduce
   - Environment info (`bin/vibe check` output)
