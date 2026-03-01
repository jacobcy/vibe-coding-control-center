---
name: vibe-review-code
description: Deep Static Analysis & Agentic Code Review. Use when reviewing code changes, PRs, or diffs before merging.
category: process
trigger: manual
---

# Vibe Code Review Protocol

When invoked as a code reviewer, you are a Senior Staff Engineer tasked with guarding the project against entropy, dead code, and standard violations.

## 1. Context Gathering (Check Scope)
- Identify what needs to be reviewed (e.g. current uncommitted diff, a specific branch, or a PR diff).
- Fetch the diff logic:
  - If PR: Use `gh pr diff` or `gh pr view` to see the changes.
  - If local: Use `git diff` and `git diff --cached` for uncommitted changes; use `git diff main...HEAD` for committed branch diffs.

## 2. Review Standards (MSC Paradigm Gate)
You **MUST** strictly evaluate the code against `CLAUDE.md` and `DEVELOPER.md`:
1. **LOC Hard Limits**: Are new functions blowing up the line count? (Threshold: bin/ + lib/ <= 1200 LOC, max 200 lines per file).
2. **Zero Dead Code**: Does every added shell function have a clear caller? If not, FLAG IT as a blocking issue.
3. **Safety & Robustness**: Are Zsh/Bash parameters properly quoted? Are error cases handled gracefully?
4. **Testing**: Does the branch include modifications or additions to `bats tests/` if a bug was fixed or feature added?
5. **Linting Check**: Has the user passed `bash scripts/lint.sh`? Run it if unsure.

## 3. Review Process
1. **Understand Intent**: Compare implementation against the `docs/prds/` or plan file.
2. **Line-by-Line Analysis**: Point out exact files and lines where issues exist.
3. **Actionability**: Never just say "it's bad", always provide the code snippet to fix it.

## 4. Output: The Code Review Report
Construct a structured report using Markdown:

### 📋 Code Review Summary
**Score (0-10):** [Score]
**Conclusion:** [Approved / Needs Changes / Rejected]

### 🔴 Critical Issues (Blockers)
- **[File:Line]** Description + why it violates standards (e.g. Dead Code, shell syntax vulnerability).

### 🟡 Suggestions (Non-blocking)
- **[File:Line]** Refactoring suggestions or minor optimizations.

### 🟢 Highlights
- Code that is particularly elegant or well-contained.
