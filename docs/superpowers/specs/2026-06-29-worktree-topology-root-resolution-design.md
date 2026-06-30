---
document_type: design
title: Worktree Topology Root Resolution
status: proposed
scope: PR 3246 repository and resource root resolution
author: Codex
created: 2026-06-29
last_updated: 2026-06-29
related_docs:
  - AGENTS.md
  - docs/standards/agent-document-lifecycle-standard.md
---

# Worktree Topology Root Resolution Design

## Goal

Guarantee correct operation for both supported repository layouts:

- non-bare main checkout: `main/.worktrees/<name>`
- bare repository: `bare_repo/.worktrees/<name>`

When a required root cannot be resolved safely, the caller must receive an
explicit diagnostic instead of a silent fallback to an unrelated directory.

## Root Semantics

The implementation must keep three paths distinct:

1. **Git common directory**: shared Git metadata returned by
   `git rev-parse --git-common-dir`.
2. **Repository management root**: the path used for shared state and worktree
   creation. This is `main` for a non-bare main checkout and `bare_repo` for a
   bare repository.
3. **Current worktree root**: checked-out files returned by
   `git rev-parse --show-toplevel` for the relevant `GitClient.cwd`.

Repository management operations use the repository management root. Source,
skill, prompt, and project-local configuration reads use the current worktree
root or the existing runtime-asset resolver.

## Resolution Design

### Repository management root

`find_repo_root()` remains the compatibility API for the repository management
root. Bare detection must inspect only `core.bare`; a `bare = true` key in any
other Git config section must not affect resolution.

`GitClient.find_repo_root()` must derive its answer through the instance command
runner so that `GitClient(cwd=...)` resolves the repository associated with that
cwd. It must not delegate to a process-global, cwd-sensitive cache.

### Checked-out resources

Resource consumers must not assume the repository management root contains a
checkout. Relative skill and prompt paths use `resolve_runtime_asset()`, which
already distinguishes bundled mechanism assets, globally installed assets, and
project-local `.vibe/` assets. Adapter resource discovery may search the current
worktree and bundled source roots, but it must validate its required marker
before accepting a candidate.

### Unsupported or malformed layouts

Required operations fail fast with a message containing:

- current cwd
- resolved Git common directory, when available
- resolved current worktree root, when available
- the required marker or path

Optional resource reads emit a warning containing the same useful path context
and return their existing optional value. They must not silently use the parent
of an unvalidated Git directory.

## Caller Boundaries

- Worktree creation, shared cache placement, and orchestra repository identity
  use the repository management root.
- Relative skills, prompts, policies, and checked-out configuration use the
  current worktree/runtime asset root.
- Existing callers that inject a `GitClient` keep mockability by calling the
  instance API.
- No new command surface or layout-specific environment variable is introduced.

## Verification Matrix

Tests must create real temporary Git repositories rather than only mocking
`get_git_common_dir()`:

| Layout | Expected management root | Expected resource root |
| --- | --- | --- |
| `main/.worktrees/topic` | `main` | `main/.worktrees/topic` or bundled runtime root |
| `bare_repo/.worktrees/topic` | `bare_repo` | `bare_repo/.worktrees/topic` or bundled runtime root |

Additional regression cases:

- `GitClient(cwd=<other repo>)` resolves that repository, independent of the
  process cwd.
- a non-core `bare = true` key does not classify a non-bare repository as bare.
- a relative skill path resolves in both supported layouts.
- a missing required marker raises an actionable diagnostic.
- an optional missing resource logs a warning and returns `None`.

Local verification remains targeted: affected unit/integration tests, mypy for
changed modules, repository lint checks for changed files, and `git diff --check`.
Full regression remains CI-owned.

## Non-goals

- Supporting arbitrary worktree layouts that Git itself cannot resolve.
- Inferring topology from directory names such as `.worktrees`.
- Refactoring unrelated shared-state or runtime-asset code.
- Adding a new CLI command or configuration option.
