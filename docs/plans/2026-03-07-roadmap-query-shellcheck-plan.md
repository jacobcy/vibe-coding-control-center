# Roadmap Query ShellCheck Fix Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the ShellCheck/parsing failures in `lib/roadmap_query.sh` so CI lint passes, rerun the verification suite, and publish the result plus review reply on PR #51.

**Architecture:** Keep `lib/roadmap_query.sh` as a small Zsh helper invoked by `bin/vibe roadmap`, but rewrite the offending multi-line heredoc/inline brace syntax to Bash-friendly constructs so `scripts/lint.sh`’s `shellcheck -s bash -S error` still succeeds. Repeat the same verification steps locally and articulate the fix/respond on GitHub.

**Tech Stack:** Zsh scripts for CLI, `shellcheck` (Bash) lint, `scripts/lint.sh`, GitHub CLI (`gh`) for PR reviews.

---

### Task 1: Make `lib/roadmap_query.sh` shellcheck-friendly

**Files:**
- Modify: `lib/roadmap_query.sh`

**Step 1: Replace the heredoc/inline braces with explicit variables**
  - Add a local `counts` variable instead of `IFS=' ' read ... <<EOF` so Bash prints a simple whitespace-separated string.
  - Use a `read -r p0_count ... <<< "$counts"` expression to parse the string.
  - Turn `_vibe_roadmap_require_file` into a multi-line function (with `if [[ -f ... ]]; then ... else ... fi`) so braces are balanced under `/bin/bash` parsing.
  - Ensure `_vibe_roadmap_common_dir`, `_vibe_roadmap_status`, and `_vibe_roadmap_has_version_goal` use conventional newline-delimited braces (no single-line definitions) to satisfy ShellCheck.
  - Keep the business logic unchanged (query registry JSON counts) and preserve quoting for external strings.

**Step 2: Run ShellCheck to confirm the parser is happy**
  - Run `shellcheck -s bash -S error lib/roadmap_query.sh`. Expected: no findings, exit code 0.

**Step 3: Commit this fix**
  - `git add lib/roadmap_query.sh`
  - `git commit -m "fix: make roadmap query shellcheck-clean"`

### Task 2: Rerun lint/test gating commands

**Files:**
- Verify: `scripts/lint.sh`
- Verify: `tests/test_install_gh_noninteractive.bats`

**Step 1: Run `scripts/lint.sh`**
  - Command: `bash scripts/lint.sh`
  - Expected: prints both layers (Zsh syntax + ShellCheck) and exits with code 0.

**Step 2: Run `bats tests/test_install_gh_noninteractive.bats`**
  - Expected: 1 test, PASS.

**Step 3: Amend commit if needed**
  - If either command generates changes (should not), stage & amend the prior commit to keep history clean (no new commit yet) unless additional work is necessary for Stage 1 fix.

### Task 3: Close the review loop on PR #51 and verify CI status

**Files:**
- None (GitHub PR review only)

**Step 1: Respond to the Copilot review summary comment**
  - Command: `gh pr review 51 --repo jacobcy/vibe-coding-control-center --comment -b "Thanks for the thorough review. ShellCheck was tripping on lib/roadmap_query.sh’s heredoc style; I rewrote that helper and reran scripts/lint.sh and the new install test locally. CI should pass now."`
  - Expected: comment posted.

**Step 2: Push the branch to update PR #51**
  - Command: `git push origin codex/roadmap-skill`
  - Expected: push succeeds, triggers CI rerun.

**Step 3: Re-check CI status**
  - Command: `gh pr checks 51 --repo jacobcy/vibe-coding-control-center`
  - Expected: “Lint & Test” job passes (green). If not, inspect logs and iterate back to Task 1.

---

Plan complete and saved to `docs/plans/2026-03-07-roadmap-query-shellcheck-plan.md`. Two execution options:
1. Subagent-Driven (this session) – fast iteration with fresh subagent per task.
2. Parallel Session (separate) – spawn new session with executing-plans.
