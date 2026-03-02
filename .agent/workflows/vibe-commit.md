---
description: Interactive Smart Commit Workflow based on diff analysis to draft Conventional Commits.
---

# Vibe Commit

**Input**: Run `/vibe-commit` to generate smart commit drafts for current changes.

**Steps**

1. **Acknowledge the command**
   Immediately say: "I will run a review-gated commit draft flow and then generate smart commit suggestions."

2. **Run orchestrator gate check first**
   You MUST invoke `vibe-orchestrator` and enter **Review Gate**.
   If Review Gate is blocked, stop and report the blocking reason.

3. **Call commit drafting skill**
   Only after Review Gate passes, invoke the `vibe-commit` skill.
   Read changes using `git status` and `git diff` / `git diff --cached` when needed.

4. **Provide verification and confirmation**
   Output grouped commit drafts and **ask for the user's explicit confirmation** before any commit execution.

5. **Post-Commit PR Proposal**
   Once the user's working tree is completely clean and all changes are committed, automatically ask if they would like to create a Pull Request directly. If yes, generate the PR Title and Body, ask for confirmation again, and then execute `gh pr create` with the generated contents.
