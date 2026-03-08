---
name: "Vibe: Commit"
description: Interactive Smart Commit Workflow based on diff analysis to draft Conventional Commits
category: Workflow
tags: [workflow, vibe, git, commit]
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
   Once the user's working tree is completely clean and all changes are committed, you may propose creating a Pull Request. Keep the wording precise: this is only a proposal to start PR publication, not a claim that the branch is ready to merge into `main`.

6. **Base Validation Before PR Draft**
   Before drafting any PR command, read `vibe flow pr --help` and treat `vibe flow pr (shell)` as the source of truth for base selection.
   If the current branch is not closest to `main`, do not imply the PR should target `main`; surface the inferred base or require an explicit `--base <ref>`.

7. **Boundary Alignment**
   Keep responsibilities explicit:
   - `/vibe-commit`: skill-layer orchestration and commit/PR draft preparation
   - `vibe flow pr`: shell-layer publication entry and PR base validation
   - `gh pr create`: underlying external tool invoked by shell, not the workflow's direct source of truth
