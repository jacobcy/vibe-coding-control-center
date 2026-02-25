---
description: Interactive Smart Commit Workflow based on diff analysis to draft Conventional Commits.
---

# Vibe Commit

**Input**: Run `/vibe-commit` to invoke intelligent git commit generation based on current changes.

**Steps**

1. **Acknowledge the command**
   Immediately say: "Invoking the vibe-commit skill to analyze your changes and draft smart commits."

2. **Call the underlying skill**
   You MUST invoke the `vibe-commit` skill. The skill handles diff reading, logical separating, and drafting of the commit messages.
   Read the changes using `git status` and `git diff` / `git diff --cached` to feed context to the skill if necessary.

3. **Provide Verification**
   Output the commit draft mapping from the vibe-commit skill and **ask for the user's explicit confirmation**.
