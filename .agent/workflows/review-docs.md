---
description: Review Documentation and Changelogs
---

# Documentation Review

**Input**: Run `/review-docs` to audit documentation PRs, new PRDs, or changes to project guidelines.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the `vibe-review-docs` skill to verify documentation quality and consistency."

2. **Call the underlying skill**
   You MUST read the instructions in `skills/vibe-review-docs/SKILL.md` and strictly follow its evaluation framework. You will review markdown files for brevity, correctness, proper naming conventions (like `.agent` vs `.agents`), and ensure `CHANGELOG.md` is updated for user-facing changes.

3. **Output the Report**
   Generate the structured Documentation Review Report as defined in the skill, highlighting required edits and clarity suggestions.
