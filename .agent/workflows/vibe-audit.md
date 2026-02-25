---
description: Perform a deep architectural audit of the project to check for design rot.
---

# Architecture Audit

**Input**: Run `/vibe-audit` to evaluate if the codebase should be refactored or rebuilt.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-audit skill to perform a deep architectural evaluation."

2. **Call the underlying skill**
   You MUST invoke the `vibe-audit` skill. The skill handles the 3-phase audit (Discovery, Analysis, Verdict). Follow the instructions in the skill exactly to complete the audit.

3. **Provide Verdict**
   Ask the user how they would like to proceed based on the skill's findings.
