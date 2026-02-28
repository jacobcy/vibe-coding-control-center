---
description: Deep Static Analysis & Agentic Code Review
---

# Code Review Protocol

**Input**: Run `/review-code` to audit current uncommitted changes, branches, or PR contents.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the `vibe-review-code` skill to perform an architectural and standards review."

2. **Call the underlying skill**
   You MUST read the instructions in `skills/vibe-review-code/SKILL.md` and strictly follow its evaluation framework. You will identify the target scope (diff or PR), cross-reference with project rules in `CLAUDE.md` and `DEVELOPER.md`, and look for dead code, LOC violations, and test coverage logic.

3. **Output the Report**
   Generate the structured Code Review Report as strictly defined in the skill, providing a Compliance Score and identifying all blocking issues.
