---
document_type: workflow
description: Verify the consistency of project memory and documents
author: Claude Sonnet 4.5
created: 2025-01-24
related_docs:
  - .agent/context/memory.md
  - .agent/context/task.md
  - SOUL.md
---

# Verify Memory Consistency

**Input**: Run `/vibe-check` to validate that project state, tasks, and governance configs align with memory records.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-check skill to verify project memory and governance consistency."

2. **Call the underlying skill**
   You MUST invoke the `vibe-check` skill. The skill will cross-reference files in `.agent/context/` and validate the `governance.yaml`.
   
3. **Report Status**
   Show the discrepancies and pass on the recommended actions from the skill to the user.
