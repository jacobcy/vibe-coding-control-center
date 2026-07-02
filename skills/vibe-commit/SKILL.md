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

## Publish Strategy

**Agent 是发布业务的 owner，负责完整判断 PR/CI/LOC/review/merge 现场。**

### 无 `pr_ref` 场景（首次发布）

1. 完成 LOC gate、两步提交纪律、push
2. 调用 `vibe3 pr create --agent` 创建 PR
3. 记录 PR 事实（`vibe3 handoff append`）
4. **显式给出业务结论**：
   - 若 PR 创建成功 → 写 handoff 说明，等待 CI/review
   - 若 PR 创建失败 → 写 blocked + reason，等待人类介入

### 已有 `pr_ref` 场景（follow-up publish）

1. 读取 CI/review/merge 现场
2. **不重复创建 PR**
3. 根据现场决定：
   - CI 失败 → 修复问题、push、写 handoff 说明
   - Review 有反馈 → 处理反馈、push、写 handoff 说明
   - Review 通过但未合并 → 写 handoff 说明，等待 merge
   - 已合并 → 进入 `/vibe-done` 流程

### 显式状态转换规则

Agent 每轮执行完成后，**必须**显式改变状态或给出业务结论：

- **交给 manager 复核** → 显式写 `state/handoff`
- **需要人类判断** → 显式写 `state/blocked` 并说明 durable reason
- **不得把"PR 存在"描述为"发布工作全部完成"**

### 禁止事项

- ❌ 仅因 PR OPEN 就认为发布完成
- ❌ 不检查 CI/review 状态就进入下一步
- ❌ 不显式写状态转换，依赖系统隐式推进
- ❌ 创建重复 PR

### Step 10: 记录完成状态

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

**留痕内容应包含**：
- PR 编号
- Issue 编号（如有）
- Branch 名称
- 提交策略（single/parallel/stacked）
- 下一步建议

**显式状态转换**：

PR 创建成功后，**必须**显式更新状态：

```bash
# 更新为 handoff 状态，等待 manager 复核
gh issue edit <issue-number> --add-label "state/handoff" --remove-label "state/merge-ready"
```

若遇到阻塞情况（如 CI 失败、权限问题），**必须**显式写 blocked：

```bash
# 记录阻塞原因
vibe3 handoff append "[vibe-commit] Blocked: <具体原因>" --actor vibe-commit --kind blocker

# 更新为 blocked 状态
gh issue edit <issue-number> --add-label "state/blocked" --remove-label "state/merge-ready"
```

若用户问"下一步是什么"，回答：
> 运行 `/vibe-integrate` 检查 CI 状态和 review，确认合并条件后推进。

**注意事项**：
- 允许：进入 `/vibe-integrate` 检查 review、CI、merge 阻塞
- 不允许：直接进入 `/vibe-done`
- 不允许：把当前 task 当作下一个新目标继续开发

## Restrictions

- **Pre-commit 硬规定**：
  - 不得使用 `git commit --no-verify` 跳过 pre-commit 检查
  - 不得在有 pre-commit 错误（如 mypy、shellcheck、LOC 超限）的情况下继续提交
  - 必须在组织 commit 分组前完成 pre-commit 验证
  - 格式化流程：对所有改动统一格式化 → 提交临时 commit → 软重置（检查是否为临时 commit）→ 分组提交
  - 不得保留单独的格式化 commit，格式化修改必须分散到各功能 commit 中
- **LOC 强制检查**：
  - 发 PR 前必须通过 LOC 检查（`ENFORCE_LOC_LIMITS=true`）
  - 超限文件必须修复或申请 exception，不允许跳过
  - 此检查与 CI 保持一致，确保本地和远程行为相同
- **主分支同步**：
  - 提交前必须检查 `origin/main` 是否有新提交
  - 冲突未解决前禁止提交
- **提交必要性检查**：
  - 若改动已不需要提交，必须用 `handoff append` 说明理由
  - 必须更新 issue 标签为 `state/handoff`，等待 manager 决定
- 不得在用户确认前静默执行 `git commit`
- 不得把"是否拆多个 PR"的判断偷换成"先发一个再说"
- 不得把 `stash` 当垃圾桶
- 不得把 `discard` 当默认处理方式
- 若发现当前 task 已有 PR 事实且用户要开始新目标，应停止并切换 task，而不是继续堆在原 task
