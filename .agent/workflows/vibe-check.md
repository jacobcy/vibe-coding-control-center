---
name: "Vibe: Check"
description: Read shell audit output, explain discrepancies, and invoke the vibe-check skill for safe shell-driven repairs.
category: Workflow
tags: [workflow, vibe, verification, shared-state]
---

# Verify Shared-State Consistency

**Input**: Run `/vibe-check` to inspect `roadmap.json`, `registry.json`, and `worktrees.json`, then repair deterministic gaps through Shell APIs when safe.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-check skill to read shell audit output and repair deterministic shared-state gaps through Shell APIs."

2. **Call the underlying skill**
   You MUST invoke the `vibe-check` skill.

3. **Respect shell / skill boundary**
   - `vibe check(shell)` only audits.
   - `vibe-check` skill interprets results and decides whether a fix is safe.
   - Shared-state writes must go through Shell APIs such as `vibe task update`.

4. **Report status**
   Show:
   - shell audit findings
   - fixes executed through shell commands
   - items requiring user confirmation
   - any missing shell capability that blocks safe repair
