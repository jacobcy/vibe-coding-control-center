# Feature Specification: Environment Isolation Baseline

**Feature Branch**: `dev/issue-3299`
**Created**: 2026-07-03
**Corrected**: 2026-07-04
**Status**: Baseline / Reverse Specification

## Purpose and truth sources

This baseline covers `src/vibe3/environment/`, `WorktreeRequirement`, runtime-session persistence, and path/root helpers used by worktree execution. Repository-management root, execution checkout, and runtime-resource root are distinct concepts.

## User Scenarios & Testing

### Scenario 1 - Permanent issue worktree

`WorktreeManager.acquire_issue_worktree(issue_number, branch)` reuses a registered worktree for the branch or creates one at `.worktrees/<branch>`. Because branch names may contain `/`, a branch such as `task/issue-123` naturally resolves under `.worktrees/task/issue-123`.

### Scenario 2 - Temporary worktree

`acquire_temporary_worktree()` uses `.worktrees/tmp/<issue_number>`, removes a stale path for the same issue, and creates a fresh worktree from the requested base. `release_temporary_worktree()` recycles it after the isolated operation.

### Scenario 3 - Runtime session registry

The runtime-session registry pre-registers launches, records running/terminal states, verifies tmux liveness when a backend is available, and marks stale/orphaned sessions. A database status alone is not conclusive proof that a tmux process is live.

### Scenario 4 - Bare repository compatibility

Code that manages repository metadata may run from a bare management root, but role execution requires a real checkout/worktree. Path helpers use repository-aware resolution rather than assuming `Path.cwd()` is the main checkout.

## Requirements

- **FR-001**: permanent issue worktrees MUST be keyed by branch and stored at `.worktrees/<branch>` unless an already registered worktree is reused.
- **FR-002**: temporary worktrees MUST use `.worktrees/tmp/<issue_number>` and MUST be released through the temporary-worktree path.
- **FR-003**: the baseline MUST NOT describe obsolete `issue-{number}-{hash}` or `temp-{hash}` naming schemes.
- **FR-004**: `WorktreeContext` MUST carry path, temporary/permanent identity, and optional branch/issue metadata.
- **FR-005**: worktree removal MUST respect live runtime-session ownership checks performed by callers/services.
- **FR-006**: session liveness MUST verify tmux where possible and MUST treat stale `starting` rows according to the registry timeout behavior.
- **FR-007**: recorded `worktree_path` is an execution-location anchor, not a substitute for repository-management-root discovery.
- **FR-008**: bare-repository compatibility MUST mean management operations can resolve shared git/runtime metadata; it MUST NOT imply agents can execute without a checkout.
- **FR-009**: this spec makes no global claim that all concurrent callers are race-free; only explicit registry, path reuse, and cleanup guards are baseline behavior.

## Key implementation PRs

| PR | Contribution |
|---|---|
| [#3246](https://github.com/jacobcy/vibe-coding-control-center/pull/3246) | Corrected bare-repository root resolution and fetch-refspec handling. |
| [#2532](https://github.com/jacobcy/vibe-coding-control-center/pull/2532) | Centralized `.git/vibe3` metadata path resolution. |
| [#2530](https://github.com/jacobcy/vibe-coding-control-center/pull/2530) | Routed worktree lifecycle state through `FlowService` rather than direct SQLite use. |
| [#1032](https://github.com/jacobcy/vibe-coding-control-center/pull/1032) | Persisted `worktree_path` for automatically created task branches. |

## Known gaps and tracking

No uncovered implementation gap was found after correcting the stale naming and over-broad concurrency wording. Topology-specific runtime-resource lookup is covered by the current root-resolution implementation and tests rather than a new issue here.

## Success Criteria

- L2/L3 paths match the code exactly.
- Bare-root and checkout responsibilities are not conflated.
- Concurrency claims are limited to mechanisms actually present in the registry/lifecycle code.

## Non-goals

- Changing worktree naming.
- Adding locks beyond current lifecycle guards.
- Defining flow cleanup policy, which belongs to spec 001.
