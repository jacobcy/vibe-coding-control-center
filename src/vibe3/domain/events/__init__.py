"""Domain events for Vibe3 lifecycle.

These events represent business state changes across all execution chains.
Event-driven architecture allows loose coupling between Usecase and Service layers.

Events are organized by execution chain:
- flow_lifecycle: L3 agent chain (planner, executor, reviewer)
- governance: L1 governance service (periodic scans)
- supervisor_apply: L2 supervisor handoff chain (lightweight governance execution)

Reference: docs/standards/vibe3-worktree-ownership-standard.md §二
"""
