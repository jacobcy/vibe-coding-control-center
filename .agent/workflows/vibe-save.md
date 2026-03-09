---
name: "Vibe: Save"
description: Save session context, tasks, and decisions to project memory
category: Workflow
tags: [workflow, vibe, memory, persistence]
---

# Save Session Context

**Input**: Run `/vibe-save` when finishing a session or reaching a milestone.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-save skill to preserve the current session context."

2. **Call the underlying skill**
   You MUST invoke the `vibe-save` skill to perform the actual saving. This skill is responsible for gathering context, refreshing `.agent/context/memory.md` and `.agent/context/task.md`, and coordinating `.agent/governance.yaml` hooks.
   Shared-state writes must go through shell APIs such as `vibe task update`; do not manually edit registry/worktree JSON files.

3. **Report Status**
   Once the skill finishes execution, provide a short summary of what was saved.
   The summary must explicitly mention: `current actor`、`flow/task`、`next step`、`capability gap`。
