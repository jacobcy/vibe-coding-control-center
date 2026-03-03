---
name: vibe-review-code
description: Deep Static Analysis & Agentic Code Review. Use when reviewing code changes before PR, or fixing code based on PR feedback. Use `vibe flow review` to check PR status.
category: process
trigger: manual
---

# Vibe Code Review Protocol

**核心职责**: 代码质量审查（PR 提交前后的深度分析）

**使用场景**:
1. **PR 前**: 在运行 `vibe flow pr` 之前，进行深度静态分析
2. **PR 后**: 根据 `vibe flow review` 的反馈修复代码

When invoked as a code reviewer, you are a Senior Staff Engineer tasked with guarding the project against entropy, dead code, and standard violations.

## 1. Context Gathering (Align Truth)
- **Identify Intent**: Run `vibe flow review` (Physical Tier 1) to determine the current state of the PR and project health.
- **Fetch Diff**: 
  - If a PR exists (opened by `flow review` or confirmed): Use `gh pr diff` to fetch the source of truth for changes.
  - If local only: Use `git diff main...HEAD`.
- If local: Use `git diff` and `git diff --cached` for uncommitted changes; use `git diff main...HEAD` for committed branch diffs.
- **Review Context**: Cross-reference with the Task README and the original goal from `.agent/context/task.md`.

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
