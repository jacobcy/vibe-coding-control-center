# Proposal: Fix Six Critical Bugs

## Why

Six critical bugs are blocking core workflows: worktree operations fail due to hardcoded `.git` paths, branch binding lacks safety checks, config compatibility is broken for cold-start scenarios, PR merge order is lost across sessions, flow-done leaves worktrees in detached HEAD state, and flow-merge uses unsafe delete-branch semantics. These issues affect daily development reliability and must be fixed to restore stable baseline operations.

## What Changes

### Bug Fixes
- **#167**: Fix hardcoded `.git` path assumptions - make all vibe commands worktree-aware by using `git rev-parse --git-dir` instead of `.git`
- **#162**: Enhance `bind-current` to infer current branch and reject binding to already-occupied branches
- **#155**: Restore config compatibility for cold-start bootstrap - ensure local gate works without pre-existing config
- **#153**: Restore stacked PR merge order tracking - persist merge dependencies across sessions
- **#144**: Fix `flow-done` closeout to avoid stranding worktrees in detached HEAD state
- **#123**: Fix `flow-merge` to avoid delete-branch semantics when worktree is still occupied

### Improvements
- **BREAKING**: Branch binding now enforces exclusivity - attempting to bind to an already-bound branch will fail
- **BREAKING**: `flow-merge` will no longer auto-delete branches if the worktree is still occupied (safety improvement)

## Capabilities

### New Capabilities
- `worktree-aware-path-resolution`: Dynamic `.git` path resolution that works in both main repo and worktree contexts
- `branch-binding-exclusivity`: Safety mechanism to prevent conflicting branch bindings
- `stacked-pr-order-persistence`: Session-spanning tracking of PR merge dependencies

### Modified Capabilities
- `vibe-task-runtime`: Enhanced to support branch inference and binding validation (relates to #162, #119)
- `flow-done-workflow`: Modified to ensure clean worktree state after closeout (relates to #144)
- `flow-merge-workflow`: Modified to respect worktree occupancy when deleting branches (relates to #123)

## Impact

### Affected Code
- `lib/core.sh` - Core path resolution logic
- `lib/task-runtime.sh` - Branch binding and runtime tracking
- `lib/flow.sh` - Flow operations (done, merge, pr)
- `lib/config.sh` - Config compatibility and bootstrap
- All vibe commands that reference `.git` paths

### Affected Workflows
- `vibe flow start` - Branch initialization
- `vibe flow done` - Worktree closeout
- `vibe flow merge` - Branch merging and cleanup
- `vibe task bind-current` - Branch binding
- Cold-start scenarios - First-time setup and config bootstrap

### Breaking Changes
1. **Branch binding exclusivity** - Code that assumes it can rebind an already-bound branch will break (intentional safety improvement)
2. **Flow-merge branch deletion** - Scripts expecting automatic branch deletion when worktree is occupied will fail (intentional safety improvement)

### Dependencies
- Requires git worktree awareness throughout the codebase
- May require migration of existing runtime state for #119, #153
- Config backward compatibility must be maintained for #155
