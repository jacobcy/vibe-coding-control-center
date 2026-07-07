---
name: vibe-commit
description: Use when the user wants to classify dirty changes, create serial commits, split work into one or more PRs, or publish the current flow without merging it.
---

# /vibe-commit - Commit And PR Publication

## Overview

`vibe-commit` turns one verified delivery target into intentional commits and a
draft PR. It owns workspace classification, the mandatory two-stage commit gate,
PR slicing, publication, and trace recording. It does not merge or close the
issue, task, or flow.

## When To Use

Use this skill when changes are ready to organize or publish. Route CI/review
convergence to `vibe-integrate` and post-merge cleanup to `vibe-done`. If the
current flow already has a PR, only review follow-up for that PR may continue in
the same flow.

## Required Reading

Read at most these three business standards before acting:

1. `docs/standards/v3/git-workflow-standard.md`
2. `docs/standards/v3/command-standard.md`
3. `docs/standards/github-labels-standard.md`

## Execution Flow

### 1. Resolve The Delivery Target

Use current conversation evidence when it is fresh; otherwise run:

```bash
vibe3 flow show
vibe3 handoff status
git branch --show-current
git status --short --branch
```

Confirm one issue, one flow, one branch, and one PR target. If the branch already
serves another PR target, stop and route through `vibe-new` instead of mixing
deliveries.

### 2. Reconcile Main And Necessity

```bash
git fetch origin main
git log HEAD..origin/main --oneline
```

Rebase onto `origin/main` when needed. A merge is allowed only when rebase would
damage an intentional history, and the reason must be recorded in handoff.
Resolve all conflicts and rerun targeted verification before continuing.

Stop if the issue is closed, replaced, or already delivered. Record that outcome
with `vibe3 handoff append`; do not manufacture a PR.

### 3. Classify The Workspace

```bash
git status --short
git diff --stat
git diff --cached --stat
GRAPHIFY_DIRTY_BEFORE=$(git status --porcelain -- graphify-out/)
```

Classify every path as `commit now`, `preserve for another target`, or `discard`.
Never use `git add .`, `git commit -a`, stash as a junk drawer, or silent discard.

Graphify policy:

- Graphify 生成物只进入独立的 `automation/graphify-sync` PR。
- Ordinary functional PRs must exclude the entire `graphify-out/` directory.
- 若 `GRAPHIFY_DIRTY_BEFORE` 非空，禁止自动 restore；first determine whether
  the changes are intentional curation, previous user work, or hook output.
- Intentional curated-label maintenance is a separate human-owned flow/branch/PR,
  never a side effect hidden inside a functional PR and never committed directly
  onto the CI-owned `automation/graphify-sync` branch.

Tell the user which files enter this delivery and which paths are preserved or
discarded before mutating the index.

### 4. Run The Mandatory Two-Stage Commit Gate

Every change round uses a real temporary commit. This is not conditional on
Black, Ruff, or another formatter changing files.

```bash
BASE_SHA=$(git rev-parse HEAD)

# Stage only the already classified commit-now files.
git add <explicit-paths>
git diff --cached --check
git diff --cached --stat

# Stage 1: run the real commit hooks.
git commit -m "temp: pre-commit validation"
```

If hooks fail, fix the reported files, stage the same delivery scope, and retry.
Never use `--no-verify`.

If `GRAPHIFY_DIRTY_BEFORE` was empty, wait for the post-commit Graphify process
to finish, confirm only generated paths became dirty, then restore them:

```bash
for _ in {1..30}; do
  pgrep -f 'graphify.*(watch|update|rebuild)' >/dev/null || break
  sleep 1
done
pgrep -f 'graphify.*(watch|update|rebuild)' >/dev/null && exit 1
git restore --worktree -- graphify-out/
```

Return the validated files to the working tree with the correct reset mode:

```bash
git reset --mixed "$BASE_SHA"
```

This is a mixed reset: the temporary commit disappears, its validated content
remains in the working tree, and the index is cleared for intentional grouping.

### 5. Create Formal Commits

For each independently reviewable group:

```bash
git add <explicit-group-paths>
git diff --cached --check
git diff --cached --stat
git commit -m "<type>(<scope>): <outcome>"
```

Formal commits run hooks again. When `GRAPHIFY_DIRTY_BEFORE` was empty, apply the
same bounded wait and `git restore --worktree -- graphify-out/` after each formal
commit. Do not carry hook output into the next group.

Before publication, enforce the functional-PR boundary:

```bash
PR_BASE=$(git merge-base origin/main HEAD)
git diff --name-only "$PR_BASE"..HEAD -- graphify-out/
```

普通功能 PR 的上述输出必须为空；非空即 Hard Block。Move intentional graph
changes to the dedicated Graphify delivery target before continuing.

### 6. Verify The Publication Set

Run targeted tests proportional to the changed files, then the mandatory local
gates:

```bash
ENFORCE_LOC_LIMITS=true bash scripts/hooks/check-per-file-loc.sh
ENFORCE_LOC_LIMITS=true bash scripts/hooks/check-test-file-loc.sh
git status --short
git log --oneline origin/main..HEAD
git branch -vv
```

Hard blocks:

- any failed test, hook, or LOC gate;
- a dirty workspace;
- `graphify-out/` in a functional PR range;
- multiple delivery targets in one branch;
- current task branch tracking `origin/main` instead of its own remote branch.

### 7. Publish One Or More PRs

Default to one PR. Split only when groups are independently deliverable and need
separate review or merge order. A new PR target requires a new flow/branch; do
not reuse the current flow as multiple PR identities.

Verify the command surface first:

```bash
vibe3 pr create --help
```

Agent publication is non-interactive and requires title and body:

```bash
vibe3 pr create --agent -t "<title>" -b "<body>"
```

Human-driven publication uses `vibe3 pr create --yes`. Both create draft PRs.
If publication fails because upstream is wrongly bound, fix the upstream and
retry; use `gh pr create` only as an explicit recovery path and record why.

### 8. Record Durable Trace

After publication:

```bash
vibe3 flow show
vibe3 handoff append \
  "[vibe-commit] PR #<number> created; strategy=<single|parallel|stacked>; next=vibe-integrate" \
  --actor vibe-commit --kind note
```

The trace must include `skill_name`, `skill_path`, `invoked_for`, `output_refs`,
and `verdict`, either in this note or the associated PR/issue record.

## Guardrails

- Never commit directly on `main` or bypass hooks with `--no-verify`.
- Never silently delete pre-existing dirty files, including Graphify artifacts.
- Never publish with unresolved conflicts, failed gates, or an unclean worktree.
- Never merge, close the issue, close the task, or close the flow here.
- Never begin a second delivery target after the current flow has a PR.
- Never create a worktree manually from this skill; route a new delivery target
  through `vibe-new` and its repository-approved lifecycle.
- Never trigger optional AI review unless the user explicitly requests it.

## Output Contract

Report:

- delivery target and commit/PR strategy;
- files committed, preserved, and discarded;
- verification commands and outcomes;
- commit SHAs and PR URL;
- remaining CI/review blockers;
- next action: `vibe-integrate`.
