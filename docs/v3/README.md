# Vibe 3.0 Parallel Rebuild Implementation Registry

> **Status:** Initializing implementation queue based on [Design Freeze](../plans/2026-03-13-vibe3-parallel-rebuild-design.md).

## Implementation Queue

| Phase | Description | Status | Spec |
|-------|-------------|--------|------|
| 01 | Command Skeleton & Entry Points | done | [01-command-and-skeleton.md](plans/01-command-and-skeleton.md) |
| 02 | Flow & Task Foundation (Python Core) | todo | [02-flow-task-foundation.md](plans/02-flow-task-foundation.md) |
| 03 | PR Domain & Publish Gate | todo | [03-pr-domain.md](plans/03-pr-domain.md) |
| 04 | Handoff, Cutover & Refresh | todo | [04-handoff-and-cutover.md](plans/04-handoff-and-cutover.md) |
| 05 | Polish & Legacy Retirement | todo | [05-polish-and-cleanup.md](plans/05-polish-and-cleanup.md) |

## Core Principles

1. **Parallelism**: Never modify `lib/` or `tests/` during initial build.
2. **Thin Shell**: All logic in Python, shell is only for glue and help.
3. **Remote-First**: GitHub is the single source of truth for roadmap and status.
4. **Verified Handoff**: Each phase must end with a `report` and `audit`.
