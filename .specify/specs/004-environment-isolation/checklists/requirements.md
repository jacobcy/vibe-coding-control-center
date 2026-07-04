# Specification Quality Checklist: Environment Isolation Baseline

**Corrected**: 2026-07-04
**Feature**: [spec.md](../spec.md)

- [x] Permanent path is `.worktrees/<branch>`.
- [x] Temporary path is `.worktrees/tmp/<issue_number>`.
- [x] Bare management root and execution checkout are separated.
- [x] Session status and verified tmux liveness are separated.
- [x] Concurrency claims do not exceed implemented guards.
- [x] Key merged PRs are linked.
