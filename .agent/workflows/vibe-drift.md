---
document_type: workflow
description: Detect and report project drift from original principles defined in SOUL.md
author: Claude Sonnet 4.5
created: 2025-01-24
related_docs:
  - SOUL.md
  - CLAUDE.md
  - .agent/context/memory.md
---

# Drift Detection

**Input**: Run `/vibe-drift` to quantify how much the project has deviated from its initial core identity.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-drift skill to check for project deviation."

2. **Call the underlying skill**
   You MUST invoke the `vibe-drift` skill. It will calculate the drift percentage based on recent commits and code changes against the `CLAUDE.md` and `SOUL.md`.

3. **Report Status**
   Present the drift percentage and recommendation to the user.
