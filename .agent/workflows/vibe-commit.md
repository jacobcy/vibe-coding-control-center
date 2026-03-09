---
name: "Vibe: Commit"
description: Review-gated commit grouping and PR slicing workflow for current branch changes
category: Workflow
tags: [workflow, vibe, git, commit, pr]
---

# Vibe Commit

**Input**: Run `/vibe-commit` to review current changes, classify them, and prepare commits/PR publication safely.

## Steps

1. **Acknowledge the command**
   Immediately say: "我会先检查工作区是否干净，再判断哪些改动该提交、暂存或丢弃，然后再决定是一条 PR 还是多条 PR。"

2. **Run orchestrator gate check first**
   You MUST invoke `vibe-orchestrator` and enter **Review Gate**.
   If Review Gate is blocked, stop and report the blocking reason.

3. **Check worktree cleanliness**
   Run `git status --short` first.
   If dirty:
   - inspect `git diff --stat` and `git diff --cached --stat`
   - read targeted diff context only as needed
   - classify changes into `commit now` / `stash` / `discard`

4. **Present change classification before commit**
   Show the user:
   - which files belong to each commit group
   - which changes should be stashed
   - which changes should be discarded
   - why

   Do not execute `git commit`, `git stash`, or destructive cleanup before explicit confirmation.

5. **Commit grouped changes**
   Only after confirmation, invoke the `vibe-commit` skill and generate grouped Conventional Commits.
   Keep `Co-authored-by` handling aligned with `docs/standards/authorship-standard.md`.

6. **Inspect commit history before PR**
   After the worktree is clean, read `vibe flow pr --help` and inspect the current branch history.
   Decide:
   - does the current branch support one PR cleanly?
   - or has it mixed multiple delivery targets?

7. **Branch semantic check**
   If the current branch name/history still matches a single delivery target, continue with one PR.
   If branch semantics are no longer suitable, or multiple PRs are needed:
   - do not publish from the current branch
   - create a new flow with `vibe flow new <name> --branch <ref>`
   - move the relevant change slice to the new branch first

   For serial multi-PR delivery, follow this exact playbook:
   - enumerate commit groups first
   - for each group, switch into a fresh flow from the correct base, usually `origin/main`
   - move only that group's commits with `git cherry-pick <commit...>`
   - verify that slice
   - publish it with `vibe flow pr --base <ref>`
   - only then continue to the next group

   Do not improvise alternate history surgery unless the user explicitly asks for it.

8. **Post-Commit PR Proposal**
   Once the correct branch is clean and semantically valid, you may propose PR publication.
   Before drafting any PR command:
   - read `vibe flow pr --help`
   - validate the correct base branch
   - avoid implying the PR should target `main` unless the shell rules support that inference

9. **Boundary Alignment**
   Keep responsibilities explicit:
   - `/vibe-commit`: skill-layer orchestration and slicing
   - `vibe flow pr`: shell-layer publication entry and base validation
   - `gh pr create`: underlying external tool, not the workflow's source of truth
