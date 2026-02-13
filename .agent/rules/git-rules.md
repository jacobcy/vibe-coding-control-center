# Git Rules & Workflow Standards

## Branching Stratergy
- **Main Branch**: `main` is protected. NEVER commit directly to `main`.
- **Feature Branches**: Must follow naming convention `feature/description` or `fix/description`.
- **Syncing**: Always pull latest `main` before starting work.

## Commit Messages
- **Format**: Conventional Commits (e.g., `feat: add new feature`, `fix: resolve crash`).
- **Atomic Commits**: Keep commits focused on a single logical change.

## Pull Requests
- **Review**: All changes to `main` must go through a Pull Request (PR).
- **Description**: PRs must have a clear description of changes and verification steps.

## Worktrees
- **Isolation**: Use `git worktree` for parallel development.
- **Cleanup**: Remove worktrees when task is complete.
