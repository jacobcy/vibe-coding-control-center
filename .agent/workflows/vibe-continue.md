---
description: Resume previous work or start a new session by loading saved task context.
---

# Resume Saved Tasks

**Input**: Run `/vibe-continue` when starting a new session or switching back to an interrupted task.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-continue skill to load project state and task backlog."

2. **Call the underlying skill**
   You MUST invoke the `vibe-continue` skill. The skill reads `.agent/context/task.md` and relevant memory files, extracts the backlog and current governance phase.
   Do not try to read and interpret these files manually; let the skill handle the logic.

3. **Report Status**
   Present the loaded context to the user based on the skill's output, and wait for their direction on what to work on next.
