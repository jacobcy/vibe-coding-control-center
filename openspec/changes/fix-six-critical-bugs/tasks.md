# Implementation Tasks: Fix Six Critical Bugs

## 1. Worktree-Aware Path Resolution (#167)

- [x] 1.1 Audit codebase for hardcoded `.git/vibe` paths
- [x] 1.2 Create utility function `vibe_git_dir()` in `lib/utils.sh` to compute git directory path
- [x] 1.3 Add path caching logic to `vibe_git_dir()` for session-level performance
- [x] 1.4 Update `lib/flow.sh` to use `vibe_git_dir()` instead of hardcoded paths
- [x] 1.5 Update `lib/task.sh` to use `vibe_git_dir()` instead of hardcoded paths
- [x] 1.6 Update `lib/task_actions.sh` to use `vibe_git_dir()` instead of hardcoded paths
- [x] 1.7 Update `lib/roadmap_store.sh` to use `vibe_git_dir()` instead of hardcoded paths
- [x] 1.8 Update `lib/flow_runtime.sh` to use `vibe_git_dir()` instead of hardcoded paths
- [x] 1.9 Test vibe commands in main repository context
- [x] 1.10 Test vibe commands in worktree context
- [x] 1.11 Test vibe commands in bare repository context (if applicable)

## 2. Branch Binding Exclusivity (#162, #119)

- [x] 2.1 Add `--bind-current` auto-inference logic to `lib/task_actions.sh`
- [x] 2.2 Implement branch conflict detection function in `lib/task_query.sh`
- [x] 2.3 Add error message formatter for binding conflicts (task ID, status, branch, worktree)
- [x] 2.4 Update `vibe task update --bind-current` to call conflict detection
- [x] 2.5 Add atomic write logic to task registry updates in `lib/task_write.sh`
- [x] 2.6 Implement `runtime_branch` persistence in `lib/task_actions.sh`
- [x] 2.7 Test auto-inference with `--bind-current` on named branch
- [x] 2.8 Test error handling in detached HEAD state
- [x] 2.9 Test conflict detection when binding occupied branch
- [x] 2.10 Test rebinding when old task is `done` or `archived`
- [x] 2.11 Test idempotent rebind (same task, same branch)

## 3. Config Compatibility for Cold-Start (#155)

- [x] 3.1 Update `.serena/project.yml` to use `languages:` array instead of `language:` string
- [x] 3.2 Verify Serena v0.1.4 compatibility with updated config
- [x] 3.3 Update `scripts/serena_gate.sh` to add `uvx --from serena` bootstrap
- [x] 3.4 Test Serena gate in fresh environment with empty cache
- [x] 3.5 Test Serena gate in CI runner environment
- [x] 3.6 Document config migration in CHANGELOG

## 4. Stacked PR Order Persistence (#153)

- [x] 4.1 Add `merge_dependencies` field to roadmap schema in `lib/roadmap_store.sh`
- [x] 4.2 Update `vibe flow pr` to record dependencies in PR metadata
- [x] 4.3 Implement `vibe roadmap dependency add` command in `lib/roadmap_dependency.sh`
- [x] 4.4 Implement `vibe roadmap dependency remove` command in `lib/roadmap_dependency.sh`
- [x] 4.5 Add circular dependency detection to dependency commands
- [x] 4.6 Add unmet dependency warning to merge operations in `lib/flow.sh`
- [x] 4.7 Ensure backward compatibility for PRs without `merge_dependencies` field
- [x] 4.8 Test dependency recording on PR creation
- [x] 4.9 Test circular dependency detection
- [x] 4.10 Test dependency loading from previous session
- [ ] 4.11 Test merge warning with unmet dependencies

## 5. Flow-Done Clean Worktree State (#144)

- [x] 5.1 Add parent branch detection logic to `lib/flow.sh` (use `git merge-base --fork-point`)
- [x] 5.2 Implement parent branch checkout before deletion in `vibe flow done`
- [x] 5.3 Add worktree occupancy check before branch deletion
- [x] 5.4 Add fallback logic when parent branch not found locally (fetch from remote)
- [x] 5.5 Test `flow done` in single worktree scenario
- [x] 5.6 Test `flow done` with multiple worktrees on same branch
- [x] 5.7 Test `flow done` when parent branch is remote-only
- [x] 5.8 Verify worktree ends on parent branch after closeout
- [x] 5.9 Test error recovery when branch deletion fails

## 6. Flow-Merge Safe Branch Deletion (#123)

- [x] 6.1 Add worktree occupancy check function to `lib/flow.sh`
- [x] 6.2 Update `vibe flow done` to check occupancy before deletion
- [x] 6.3 Implement warning message formatter for occupied branches
- [x] 6.4 Ensure merge succeeds even when deletion is skipped
- [x] 6.5 Test merge with branch not in use
- [x] 6.6 Test merge with branch occupied in one worktree
- [x] 6.7 Test merge with branch occupied in multiple worktrees
- [x] 6.8 Test merge when worktree check fails (graceful degradation)
- [x] 6.9 Verify exit code reflects merge success, not deletion status

## 7. Integration Testing & Validation

- [x] 7.1 Create integration test script for worktree scenarios
- [x] 7.2 Run full test suite in main repository context
- [x] 7.3 Run full test suite in worktree context
- [x] 7.4 Test all 6 bug fixes together in realistic workflow
- [x] 7.5 Verify no regressions in existing tests
- [x] 7.6 Update documentation with behavior changes
- [x] 7.7 Update CHANGELOG with breaking changes and migration notes

## 8. Bug-Specific Verification

- [x] 8.1 Verify #167: `vibe flow done` works in worktree context
- [x] 8.2 Verify #162: `--bind-current` auto-infers branch and prevents conflicts
- [x] 8.3 Verify #155: Serena gate works in fresh environment
- [x] 8.4 Verify #153: PR merge dependencies persist across sessions
- [x] 8.5 Verify #144: Worktree not in detached HEAD after `flow done`
- [x] 8.6 Verify #123: `flow merge` warns instead of deleting occupied branches

## 9. Documentation & Communication

- [x] 9.1 Update DEVELOPER.md with worktree-aware development notes
- [x] 9.2 Document breaking changes in CHANGELOG.md
- [x] 9.3 Add migration guide for `.serena/project.yml` change
- [x] 9.4 Close bug issues with verification references