---
name: vibe-review-code
description: Use when the user wants a structured code review for local or PR-bound source changes, asks for a pre-PR implementation audit, or wants fixes validated against code review feedback. Do not use for docs-only review, concept governance, PR publishing, merging, or CI debugging.
---

# Vibe Code Review Protocol

## Overview

`vibe-review-code` is the human-style code review skill for source changes in this repository.

Your job is to find defects that can cause wrong behavior, broken automation, unsafe state transitions, or missing verification. Lead with actionable findings. Do not drift into style preferences, broad refactors, or historical cleanup unless the current change makes them risky.

This skill reviews code; it does not publish PRs, merge branches, repair CI, or own documentation governance.

## Required Reading

Read these before judging severity:

1. `.agent/policies/review.md`
2. `.agent/policies/common.md`
3. `docs/standards/quality-control-standard.md`

Use `CLAUDE.md` / `AGENTS.md` as project-level hard rules when present, but keep the review skill's required standard list to the three files above.

## When to Use

Use this skill when:

- The user asks to review source code, a local diff, a branch, or an existing PR.
- The user asks for a pre-PR implementation audit.
- The user asks whether PR review feedback was correctly addressed.
- The change includes source files, tests, CLI behavior, prompt/context builders, shared-state code, or automation logic.

Route elsewhere when:

- The request is docs-only, standard governance, changelog quality, or concept drift: use `vibe-review-docs`.
- The request is to commit, push, label, or open a PR: use `vibe-commit` / GitHub publishing flow.
- The request is to debug failing GitHub Actions: use the CI-focused GitHub workflow.
- The request is to merge or land PRs: use integration flow.

## Guardrails

- 仓库真源优先：review evidence must come from local source, GitHub PR data, `vibe3 inspect`, tests, and current docs.
- Do not run another review runner as the default first step. `vibe3 review pr/base` launches the automated review pipeline and is optional cross-check only when explicitly useful.
- Do not use subagents unless the user explicitly asks for delegated or parallel agent work and the host environment allows it.
- Do not cross worktree boundaries. Review the current checkout and the requested PR/diff only.
- Do not edit code while reviewing unless the user explicitly asks you to fix findings.
- Never claim completion without verification evidence.
- Use `uv run` for all Python project commands.
- Do not write directly to `.git/vibe3` shared files; use `uv run python src/vibe3/cli.py handoff append ...` if review observations need internal handoff.

## Execution Flow

### 1. Resolve Scope

Identify the review target:

- Existing PR: use `gh pr view <number> --json ...` and `gh pr diff <number>`.
- Current branch: use `git status --short --branch` and `git diff <base>...HEAD`.
- Local uncommitted work: use `git diff` and `git diff --cached`.

For opened PRs, GitHub PR metadata and PR diff are the source of truth for what reviewers will see. For local-only reviews, the local worktree and index are the source of truth.

### 2. Gather Project Context

**关键区分**：本地开发 vs 远程审查

#### 本地开发（当前 worktree = PR 开发分支）

使用共享状态命令获取上下文：

```bash
uv run python src/vibe3/cli.py handoff status $(git branch --show-current)
uv run python src/vibe3/cli.py task show
```

If these commands fail because the branch has no bound flow, continue reviewing the requested diff and state the limitation.

#### 远程审查（当前 worktree ≠ PR 开发分支）

远程审查时，GitHub comments 是跨机器、跨 agent 的共享现场。不要把本地 handoff 当作唯一真源。

**自动 flow 分支**：

- `task/issue-123` and `dev/issue-123`: infer the issue number and read issue
  comments as the remote handoff / decision history.

```bash
PR_BRANCH=$(gh pr view <number> --json headRefName -q .headRefName)
if echo "$PR_BRANCH" | grep -qE '^(task|dev)/issue-[0-9]+'; then
  ISSUE_NUM=$(echo "$PR_BRANCH" | grep -oE 'issue-[0-9]+' | grep -oE '[0-9]+')
  gh issue view "$ISSUE_NUM" --comments
fi
gh pr view <number> --comments
```

**人机合作分支**：

- Branch names such as `codex/pr-123-*` do not imply an issue number.
- Do not infer an issue number from these branch names.
- Treat PR body, PR comments, and human review comments as the primary remote
  context.
- Explicitly state that issue comments are unavailable for a non-flow branch.

**远程审查上下文优先级**：

1. **PR comments** — 审查历史、人类意见和团队共享现场
2. **Issue comments** — 仅自动 flow 分支的 agent 决策过程
3. **PR description** — 改动摘要
4. **Local handoff** — 仅本地开发分支可用，不作为远程审查前提

### 3. Run Impact Analysis

Before assigning severity, collect impact evidence with `inspect`:

```bash
# Branch-level risk and changed symbols
uv run python src/vibe3/cli.py inspect base --json

# Project-level structure change vs branch baseline, when a baseline exists
uv run python src/vibe3/cli.py snapshot diff --quiet

# Commit-level impact when reviewing specific commits
uv run python src/vibe3/cli.py inspect commit <sha> --json

# Symbol usage and Python file structure
uv run python src/vibe3/cli.py inspect symbols <file>
uv run python src/vibe3/cli.py inspect symbols <file>:<symbol>
uv run python src/vibe3/cli.py inspect files <python-file-or-python-dir>
```

Use `rg` only for exact literals such as error messages, command names, config keys, paths, or prompt text. Do not replace impact analysis with plain text search.

`inspect files` is a Python structure tool. For Markdown, YAML, JSON, shell snippets, or other non-Python files, review the diff directly and use `rg` plus the relevant standards instead of forcing `inspect files`.

If `snapshot diff` reports that no branch baseline exists, do not block the review solely on that. Fall back to `uv run python src/vibe3/cli.py snapshot diff latest --quiet` when a latest snapshot comparison is useful, and record the missing baseline as a verification limitation.

For CLI changes, also use:

```bash
uv run python src/vibe3/cli.py <command> --help
uv run python src/vibe3/cli.py inspect commands <command> [subcommand]
```

### 4. Review The Diff

Prioritize findings in this order:

1. Correctness: invalid logic, missing boundary handling, broken output contracts, incomplete error paths.
2. Regression risk: public command behavior, prompt/context construction, config/default mismatches, backward compatibility.
3. Project boundary violations: bypassed handoff truth, direct shared-state writes, cross-worktree assumptions, missing `uv run`.
4. Stability and safety: external command invocation, input handling, credentials, recovery paths.

For every changed function/class/command with meaningful behavior, check:

- Who calls it or consumes its output?
- Did any signature, event type, data field, command option, or output contract change?
- Are all callers and tests updated?
- Is any new code unreachable, duplicated, or unused?
- Does the verification evidence exercise the actual failure mode?

### 5. Verify

Run targeted verification proportional to risk:

```bash
uv run ruff check <changed-src-or-tests>
uv run pytest <targeted-tests>
```

Do not repeatedly run full `uv run pytest` in the same turn unless the user explicitly asks or a CI-only failure requires it. If you cannot run a relevant check, say why.

### 6. Optional Cross-Check

Use the automated review runner only as a secondary comparison, not as the review source of truth:

```bash
uv run python src/vibe3/cli.py review pr <number> --dry-run
uv run python src/vibe3/cli.py review base --dry-run
```

Run non-dry review commands only when the user explicitly wants the automated review pipeline to execute.

### 7. Record Handoff When Useful

If the review produces internal context that future agents need, append a concise handoff note:

```bash
uv run python src/vibe3/cli.py handoff append "vibe-review-code: <summary>" --actor vibe-review-code --kind finding
```

Use `--kind finding|blocker|note|next` according to the handoff command help. Do not invent unsupported kinds.

## Finding Standards

Report only actionable findings. Each finding must include:

- `file/function`
- issue
- failure mode
- minimal fix

Severity:

- `Blocking`: broken behavior, unsafe automation, shared-state boundary violation, broken machine-consumed output, or failed critical verification.
- `Major`: should fix before merge; clear regression risk, missing caller update, missing test for risky behavior, or insufficient evidence for the claim.
- `Minor`: real issue with limited blast radius or maintainability risk introduced by the change.
- `Nit`: small clarity issue that is genuinely worth mentioning.

When using the Codex app's inline review format, emit one `::code-comment{...}` per finding with tight line ranges and priority mapped to severity.

If no issues are found, say so plainly and mention remaining test gaps or residual risk.

## Output Contract

Lead with findings, ordered by severity. Keep summaries secondary.

Recommended shape:

```markdown
## Findings

- [Blocking] path:line `function`
  - Issue:
  - Failure mode:
  - Minimal fix:

## Verification

- Passed:
- Not run:

## Verdict

PASS | MAJOR | BLOCK
```

For brief reviews, a concise findings-first response is enough, but it must still include verification evidence.
