---
description: Save session context, tasks, and decisions to project memory.
---

# Save Session Context

**Input**: Run `/vibe-save` when finishing a session or reaching a milestone.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-save skill to preserve the current session context."

2. **Call the underlying skill**
   You MUST invoke the `vibe-save` skill to perform the actual saving. This skill is responsible for gathering the context and writing to `.agent/context/memory.md` and related topic files, and it handles `.agent/governance.yaml` hooks.
   Do not try to write the files yourself manually; let the skill do it.

3. **Report Status**
   Once the skill finishes execution, provide a short summary of what was saved.
