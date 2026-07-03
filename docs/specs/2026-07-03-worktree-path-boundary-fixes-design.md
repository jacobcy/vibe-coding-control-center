---
document_type: design
title: Worktree Path Boundary Fixes
status: approved
scope: PR 3301 follow-up path correctness
author: Codex
created: 2026-07-03
last_updated: 2026-07-03
related_docs:
  - docs/standards/agent-document-lifecycle-standard.md
  - docs/specs/2026-05-18-worktree-path-recording-design.md
---

# Worktree Path Boundary Fixes

## Goal

Complete the path-boundary correction discovered while reviewing PR #3301 so
that both supported layouts behave consistently:

- bare repository: `bare_repo/.worktrees/<name>`
- non-bare main checkout: `main/.worktrees/<name>`

## Path Semantics

The implementation keeps two path roles distinct:

- `repo_path` is the repository management root. It is valid for Git worktree
  management and for locating the Git common directory.
- `wt_path` is a checked-out worktree root. It is valid for source files,
  project configuration, initialization scripts, and execution cwd.

A repository management root must never be returned as an execution cwd unless
Git proves that it is also a registered checkout.

## Changes

### Worktree resolution

Remove the `is_current_branch(repo_path, branch)` shortcut from
`WorktreeLifecycle.find_or_create_worktree_for_branch()`. A bare repository has
a symbolic `HEAD` even though it has no checkout, so branch-name equality does
not prove that `repo_path` is a usable worktree. The existing
`find_worktree_for_branch()` path is authoritative for both layouts and already
returns the registered checkout path.

For `resolve_bootstrap_worktree_context(use_worktree=False)`, resolve an
existing registered checkout for the requested branch. If none exists, raise an
explicit `SystemError` instead of returning the management root as a checkout.

### V2 initialization

Change `_vibe_worktree_run_init()` to resolve `scripts/init.sh` from
`worktree_path`. Keep `repo_root` only if another management operation needs it;
otherwise remove the unused parameter and update its caller. The script must
execute with `worktree_path` as cwd.

### SQLite shared-state resolution

Change `SQLiteClient.from_repo_path()` to ask `GitClient(cwd=repo_path)` for the
absolute Git common directory. Store `handoff.db` beneath that directory's
`vibe3/` folder. This yields `<main>/.git/vibe3/handoff.db` for non-bare repos
and `<bare_repo>/vibe3/handoff.db` for true bare repos.

Do not infer the Git common directory by appending `.git` to `repo_path`.

## Error Handling

- Missing checkout for `use_worktree=False` is an explicit `SystemError`.
- Git common-directory resolution continues to use the existing `GitError`
  contract.
- Worktree initialization remains best-effort and non-blocking.

## Verification

Tests must fail against the current implementation before production changes:

1. A true bare repository must not be treated as a current checkout merely
   because its symbolic `HEAD` matches the requested branch.
2. `use_worktree=False` must reuse a registered checkout and reject a branch
   with no checkout.
3. The V2 init helper must execute the init script found only under the new
   worktree.
4. `SQLiteClient.from_repo_path()` must place its database under the real Git
   common directory for both bare and non-bare repositories.
5. Existing worktree lifecycle, SQLite, and V2 alias tests must remain green.

Local verification is targeted: affected pytest and Bats suites, Ruff, mypy,
shell syntax checks, and `git diff --check`. Full regression remains CI-owned.

## Non-goals

- Redesigning worktree naming conventions.
- Changing worktree creation or cleanup policy.
- Refactoring unrelated path consumers.
- Changing the non-blocking behavior of `scripts/init.sh`.
