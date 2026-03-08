---
name: "Vibe: Check"
description: Read shell audit output, explain task-flow/runtime discrepancies, and invoke the vibe-check skill for safe shell-driven repairs.
category: Workflow
tags: [workflow, vibe, verification, shared-state]
---

# Verify Task-Flow Consistency

**Input**: Run `/vibe-check` to inspect task-flow/runtime consistency and repair deterministic task-worktree binding gaps through Shell APIs when safe.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-check skill to read shell audit output and repair deterministic shared-state gaps through Shell APIs."

2. **Call the underlying skill**
   You MUST invoke the `vibe-check` skill.

3. **Respect shell / skill boundary**
   - `vibe check(shell)` only audits.
   - `vibe-check` skill only handles `task <-> flow` / runtime repair.
   - Shared-state writes must go through Shell APIs such as `vibe task update`.
   - `roadmap <-> task` repair belongs to `vibe-task`, not `vibe-check`.

4. **Report status**
   Show:
   - shell audit findings
   - fixes executed through shell commands
   - items requiring user confirmation
   - any missing shell capability that blocks safe repair
