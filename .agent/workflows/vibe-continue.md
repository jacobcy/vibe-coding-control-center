---
name: "Vibe: Continue"
description: Resume previous work or start a new session by loading saved task context
category: Workflow
tags: [workflow, vibe, context, resume]
---

# Resume Saved Tasks

**Input**: Run `/vibe-continue` when starting a new session or switching back to an interrupted task.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-continue skill to load project state and task backlog."

2. **Identity and shell check**
   Confirm the current executing agent identity first.
   If you need shell context, use existing `vibe <command>` tools such as `vibe flow status`; do not invent `vibe flow continue`.
   Compare the current agent identity with `git config user.name`.
   If the identity is missing or mismatched, run `wtinit <agent>` before continuing.

3. **Call the underlying skill**
   You MUST invoke the `vibe-continue` skill. The skill reads `.agent/context/task.md` and relevant memory files, extracts the backlog and current governance phase.
   Do not try to read and interpret these files manually; let the skill handle the logic.

4. **Report Status**
   Present the loaded context to the user based on the skill's output.
   Include one explicit line: `当前操作者: <agent>`.
   Then wait for their direction on what to work on next.
