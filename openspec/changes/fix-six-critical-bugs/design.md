# Design: Fix Six Critical Bugs

## Context

Vibe Center is a development orchestration tool that manages toolchains, keys, worktree/tmux workflows, and agent rules. The codebase consists of shell scripts organized in `lib/`, `lib/alias/`, and `scripts/` directories.

The system operates on a three-tier architecture:
- **Tier 3 (Supervisor)**: Governance and flow control
- **Tier 2 (Skills)**: Context-aware orchestration
- **Tier 1 (Shell)**: Atomic capabilities and state access

Current state has six critical bugs affecting daily development:
1. **#167**: Commands fail in worktree environments due to hardcoded `.git` paths
2. **#162**: Branch binding lacks inference and conflict detection
3. **#155**: Config compatibility broken for cold-start scenarios
4. **#153**: Stacked PR merge order lost across sessions
5. **#144**: `flow-done` leaves worktrees in detached HEAD
6. **#123**: `flow-merge` uses unsafe delete-branch semantics

These bugs share common themes: worktree awareness, state persistence, and safety checks.

## Goals / Non-Goals

**Goals:**
- Make all vibe commands worktree-aware (fix #167)
- Add branch binding exclusivity and auto-inference (fix #162, #119)
- Restore config compatibility for cold-start scenarios (fix #155)
- Persist PR merge dependencies across sessions (fix #153)
- Ensure clean worktree state after `flow-done` (fix #144)
- Prevent unsafe branch deletion when worktree is occupied (fix #123)

**Non-Goals:**
- Refactoring unrelated code paths
- Adding new features beyond bug fixes
- Changing the three-tier architecture
- Migrating to a different language or framework

## Decisions

### Decision 1: Worktree-Aware Path Resolution (#167)

**Choice**: Replace all hardcoded `.git/vibe` paths with `$(git rev-parse --git-dir)/vibe`

**Rationale**:
- `git rev-parse --git-dir` returns the actual git directory path in both main repo and worktree contexts
- In main repo: returns `.git`
- In worktree: returns `/path/to/main/.git/worktrees/<name>`
- Minimal code change with maximum compatibility

**Alternatives considered**:
- **Detect worktree and branch logic**: More complex, requires conditional branching
- **Use environment variables**: Requires setup, less portable
- **Git aliases**: Doesn't solve the path resolution issue

**Implementation**:
```bash
# Before:
VIBE_DIR=".git/vibe"

# After:
VIBE_DIR="$(git rev-parse --git-dir)/vibe"
```

**Impact**: All files in `lib/` that reference `.git/vibe` need updating. Critical files:
- `lib/flow.sh`
- `lib/task.sh`
- `lib/task_actions.sh`
- `lib/roadmap_store.sh`

### Decision 2: Branch Binding Exclusivity (#162)

**Choice**: Add conflict detection and auto-inference to `vibe task bind-current`

**Rationale**:
- Current design allows multiple tasks to bind the same branch, causing state confusion
- Auto-inference reduces manual input and errors
- Explicit failure is safer than silent conflicts

**Alternatives considered**:
- **Allow rebinding with warning**: Too permissive, hides real issues
- **Auto-cleanup old bindings**: Risky, could delete active work
- **Namespace branches per task**: Complex, changes branch naming scheme

**Implementation**:
1. Read current branch: `git branch --show-current`
2. Query existing bindings: `jq -r '.[] | select(.runtime_branch == $branch)' .git/vibe/registry.json`
3. If conflict found, fail with error showing:
   - Conflicting task ID
   - Task status
   - Branch name
   - Worktree path (if available)
4. If no conflict, persist binding to registry

**Breaking change**: Code that relies on rebinding occupied branches will fail (intentional).

### Decision 3: Config Compatibility for Cold-Start (#155)

**Choice**: Fix `.serena/project.yml` schema and restore `uvx` self-bootstrapping in `scripts/serena_gate.sh`

**Rationale**:
- Serena v0.1.4 requires `languages:` array, not `language:` string
- `uvx --from serena` ensures dependency availability without cache assumptions
- Fresh environments (new machines, CI, cleaned caches) need explicit bootstrap

**Alternatives considered**:
- **Pin Serena version**: Doesn't solve the schema mismatch
- **Add setup documentation**: Doesn't prevent failures
- **Vendor Serena**: Overkill, adds maintenance burden

**Implementation**:
```yaml
# Before (.serena/project.yml):
language: bash

# After:
languages:
  - bash
```

```bash
# In scripts/serena_gate.sh:
# Ensure Serena is available before use
uvx --from serena serena --version
```

### Decision 4: Stacked PR Merge Order Persistence (#153)

**Choice**: Add `merge_dependencies` field to PR metadata in `roadmap.json`

**Rationale**:
- Current state doesn't track which PRs must merge before others
- Lost between sessions, causing merge order violations
- Simple field addition preserves order without complex graph logic

**Alternatives considered**:
- **External dependency file**: Adds another state file to manage
- **GitHub labels**: Not reliable, can be edited independently
- **PR description parsing**: Fragile, relies on formatting

**Implementation**:
```json
{
  "prs": {
    "123": {
      "url": "https://github.com/...",
      "merge_dependencies": ["122", "121"]
    }
  }
}
```

**Migration**: Existing PRs without dependencies can be updated incrementally.

### Decision 5: Clean Worktree State After flow-done (#144)

**Choice**: Check out parent branch before worktree cleanup in `flow-done`

**Rationale**:
- Current code deletes branch while worktree HEAD is on it → detached HEAD
- Checking out `main` (or parent branch) first ensures clean state
- Matches user mental model of "done means back to main"

**Alternatives considered**:
- **Leave in detached HEAD**: Confusing, poor UX
- **Delete worktree entirely**: Too aggressive, user might want to keep it
- **Ask user which branch**: Adds friction to common workflow

**Implementation**:
```bash
# In flow-done:
# 1. Get parent branch (usually main)
PARENT_BRANCH=$(git merge-base --fork-point main HEAD 2>/dev/null || echo "main")

# 2. Check out parent branch
git checkout "$PARENT_BRANCH"

# 3. Then proceed with branch deletion
git branch -D "$BRANCH"
```

### Decision 6: Safe Branch Deletion in flow-merge (#123)

**Choice**: Check worktree occupancy before branch deletion

**Rationale**:
- Deleting a branch that's checked out in a worktree causes issues
- Current code auto-deletes without checking
- Safety check prevents corruption

**Alternatives considered**:
- **Always delete**: Current behavior, causes issues
- **Never delete**: Too conservative, leaves clutter
- **Prompt user**: Adds friction to automation

**Implementation**:
```bash
# Before deleting branch:
WORKTREES=$(git worktree list --porcelain | grep "branch: $BRANCH" || true)

if [ -n "$WORKTREES" ]; then
  echo "Warning: Branch '$BRANCH' is still checked out in a worktree"
  echo "Skipping branch deletion. Remove worktree first if needed."
  # Don't delete
else
  git branch -D "$BRANCH"
fi
```

**Breaking change**: Scripts expecting auto-deletion of occupied branches will see warning instead (intentional safety improvement).

## Risks / Trade-offs

### Risk 1: Worktree Path Resolution Performance
- **Risk**: `git rev-parse --git-dir` called frequently could slow down commands
- **Mitigation**: Cache result in environment variable for shell session
- **Fallback**: Acceptable overhead for correctness

### Risk 2: Breaking Changes for Existing Workflows
- **Risk**: Branch binding exclusivity and safe deletion change behavior
- **Mitigation**: Clear error messages guide users to correct behavior
- **Acceptance**: Breaking changes are intentional safety improvements

### Risk 3: Config Migration Complexity
- **Risk**: Existing `.serena/project.yml` files need manual update
- **Mitigation**: Document migration steps in CHANGELOG
- **Scope**: Only affects users running Serena gate locally

### Risk 4: State File Consistency
- **Risk**: Adding fields to `roadmap.json` could cause format issues
- **Mitigation**: Use `jq` defaults for missing fields
- **Testing**: Verify with existing roadmap files

### Trade-off: Safety vs. Convenience
- **Choice**: Prioritize safety (exclusivity checks, occupancy checks) over convenience
- **Rationale**: Silent data corruption is worse than explicit errors
- **Documentation**: Update error messages to guide recovery

## Migration Plan

### Phase 1: Worktree Awareness (#167)
1. Audit all `.git/vibe` references in codebase
2. Replace with `$(git rev-parse --git-dir)/vibe`
3. Test in main repo and worktree contexts
4. Deploy immediately (no state migration needed)

### Phase 2: Safety Checks (#162, #123, #144)
1. Add conflict detection to `bind-current`
2. Add occupancy check to `flow-merge`
3. Add checkout logic to `flow-done`
4. Test with various worktree scenarios
5. Deploy with clear error messages

### Phase 3: Config Compatibility (#155)
1. Update `.serena/project.yml` schema
2. Add `uvx` bootstrap to `serena_gate.sh`
3. Test in fresh environment (empty cache)
4. Document in CHANGELOG

### Phase 4: State Persistence (#153)
1. Add `merge_dependencies` field to roadmap schema
2. Update PR creation to record dependencies
3. Update merge logic to respect dependencies
4. Migrate existing PRs incrementally

### Rollback Strategy
- Each fix is independent and can be reverted individually
- Config changes are backward compatible (old files still parse)
- Safety checks can be disabled with flags if needed (future enhancement)

## Open Questions

1. **Performance impact of frequent `git rev-parse` calls?**
   - Need to benchmark in large repositories
   - May need caching strategy if overhead is significant

2. **Should branch binding exclusivity be configurable?**
   - Current design: always enforce
   - Alternative: add `--force` flag for advanced users
   - Decision: Start strict, add escape hatch if needed

3. **How to handle circular merge dependencies?**
   - Current design: doesn't detect cycles
   - May need cycle detection in future
   - For now: rely on user to specify correct order

4. **Config migration automation?**
   - Current plan: manual update documented in CHANGELOG
   - Alternative: add migration script
   - Decision: Manual is acceptable for single-file config
