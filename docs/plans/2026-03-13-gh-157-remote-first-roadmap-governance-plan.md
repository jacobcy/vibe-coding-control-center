---
document_type: plan
title: GH-157 Remote-First Roadmap Governance Plan
status: proposed
author: GPT-5 Codex
created: 2026-03-13
last_updated: 2026-03-13
related_docs:
  - docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-design.md
  - docs/plans/2026-03-13-gh-157-semantic-cleanup-prerequisite-plan.md
  - docs/plans/2026-03-13-gh-157-worktrees-json-retirement-plan.md
  - docs/standards/v2/data-model-standard.md
  - docs/standards/v2/command-standard.md
  - docs/standards/v2/git-workflow-standard.md
related_issues:
  - gh-157
  - gh-158
  - gh-100
  - gh-101
  - gh-105
  - gh-122
---

# GH-157 Remote-First Roadmap Governance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将当前 roadmap / issue / task / flow 的治理口径收敛到“GitHub 真源优先，本地只做 mirror / cache / backup”，并按最小依赖顺序拆出可落地实施阶段。

**Architecture:** 先完成语义清理前置条件：冻结对象边界、把 `worktrees.json` 明确降级到待清退兼容层、把 `roadmap.json` 明确收敛成 projection/cache。然后再解除 task 对 roadmap mirror 的硬依赖，重构 `vibe roadmap sync` 为 remote-first projection，最后统一 PR/issue/closeout 的交付约束。

**Tech Stack:** Zsh, jq, GitHub CLI, GitHub GraphQL/API, Bats, Markdown

---

## Goal / Non-goals

**Goal**
- 先完成 `docs/plans/2026-03-13-gh-157-semantic-cleanup-prerequisite-plan.md`
- 固化 `#157/#158` 的总设计，明确总 issue / 分 issue / 先后依赖
- 让 execution 入口不再被 roadmap mirror 阻塞
- 让 roadmap sync 明确变成 GitHub Project / issue relations 的本地 projection
- 为后续串行 PR、parent/sub-issue、dependency、closeout 规则提供统一口径

**Non-goals**
- 本轮不一次性完成所有治理 issue
- 本轮不把 parent issue 自动关闭当作核心交付承诺
- 本轮不引入本地长期 issue registry
- 本轮不把 GitHub Project 变成 execution 层真源

## Delivery Map

### 总 issue
- `#157`: 治理母题与收口范围

### 总设计
- `#158`: 远端真源 + local-first 例外 + task 直锚 issue

### 前置条件
- 语义清理：冻结 `worktree / flow / branch / repo issue / task issue`
- `worktrees.json` 清退：先清残留、再退出主模型

### 设计支撑
- `#100`: 依赖语义与 ready/blocked 视图
- `#101`: issue -> Project intake gate
- `#105`: intake view 而非长期本地 issue 真源

### 后置实现
- `#122`: intake 性能优化，必须等 sync 语义稳定后再做
- `#119/#152/#153/#154/#155`: 属于同一治理母题，但不阻塞总设计冻结

## Phase Plan

### Precondition Phase: 先完成语义清理

**Input**
- `docs/plans/2026-03-13-gh-157-semantic-cleanup-prerequisite-plan.md`
- `docs/plans/2026-03-13-gh-157-worktrees-json-retirement-plan.md`

**Must finish before continuing**
- 标准层对象边界冻结
- `worktrees.json` 不再被设计文档描述成长期现场真源
- `roadmap.json` 统一表述为 mirror / cache / projection / backup
- `task issue` 是否进入正式语义已有明确结论

若以上未完成，不进入下面各实现 phase。

### Phase 1: 冻结 remote-first 数据模型

**Files**
- Modify: `docs/standards/v2/data-model-standard.md`
- Modify: `docs/standards/v2/command-standard.md`
- Modify: `docs/standards/glossary.md`
- Modify: `docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-design.md`

**Step 1: 固化对象锚点定义**

- 把 `task` 的强锚点明确成 `issue_refs + spec_standard/spec_ref`
- 明确 `task issue` 是 `repo issue` 的 execution role，而不是新的平行共享状态实体
- 把 `roadmap_item_ids` 明确成可选桥接，不是 execution gate
- 把 `roadmap item` 明确成 GitHub Project projection，而不是 execution 层真源

**Step 2: 固化 local-first 例外边界**

- 明确 `vibe roadmap add --local` 是显式例外，不是默认入口
- 明确 local draft 只用于规划草稿，不覆盖 GitHub 已原生支持的关系语义
- 明确 `roadmap.json` 当前保留的主要理由是 cache / projection / backup，而不是 execution 身份真源

**Step 3: 固化 sync 方向**

- 在标准里拆出 `pull` 与 `push` 两类语义
- 明确 `roadmap sync` 不再承担 execution gate 解释职责

**Step 4: 文档复核**

Run:

```bash
rg -n "roadmap item|execution record|issue_refs|Project item mirror|sync" docs/standards docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-design.md
```

Expected:
- 标准与设计文档对“远端真源 / 本地 projection”口径一致

### Phase 2: 解耦 task 创建 gate

**Files**
- Modify: `lib/task_actions.sh`
- Modify: `lib/task_help.sh`
- Modify: `skills/vibe-start/SKILL.md`
- Modify: `docs/standards/v2/command-standard.md`
- Test: `tests/task/*.bats`

**Step 1: 先写失败测试**

- 为 `task add` / `vibe-start` 增加回归测试：
  - 有 `issue_refs + spec_*` 但没有 roadmap item 时，task 仍可创建
  - 缺 spec 时仍拒绝
  - roadmap item 若传入，仍校验存在性并回写 bridge

**Step 2: 修改 shell gate**

- 保留 plan/spec 绑定要求
- 去掉“必须先 create/select roadmap item”的强耦合心智
- 让错误信息反映真实 gate，而不是把 roadmap 说成硬前置

**Step 3: 更新帮助与 skill 文案**

- `task add`
- `vibe-start`
- 相关 standard 文案

**Step 4: 验证**

Run:

```bash
bats tests/task
bash scripts/lint.sh
```

Expected:
- task 能从 issue + spec 正常起步
- roadmap item 仍可作为可选桥接

### Phase 3: 重构 roadmap sync 为 remote-first projection

**Files**
- Modify: `lib/roadmap_project_sync.sh`
- Modify: `lib/roadmap_github_api.sh`
- Modify: `lib/roadmap_issue_intake.sh`
- Modify: `lib/roadmap_store.sh`
- Modify: `lib/roadmap.sh`
- Test: `tests/roadmap/*.bats`

**Step 1: 先写合同测试**

- pull 远端 issue dependency
- pull parent/sub-issue hierarchy 能力对应的本地 projection
- push local draft 时只处理显式 local item
- 远端已有关系时，本地只 mirror，不重新定义

**Step 2: 明确 item 生命周期**

- remote-backed item
- local draft item
- local draft push 后回填 remote id

**Step 3: 清理 sync 语义混杂**

- 把 bootstrap、intake、refresh、push 的内部阶段显式分开
- 保持 CLI 外部入口尽量稳定，内部 contract 先清晰

**Step 4: 回收 dependency / hierarchy**

- 让本地 roadmap view 能读到远端 blocked-by / blocking
- 若 hierarchy 需要本地字段，确保其语义是 mirror，不是另一套真源

**Step 5: 验证**

Run:

```bash
bats tests/roadmap
bash scripts/lint.sh
```

Expected:
- sync 结果可以解释 issue dependency / sub-issue hierarchy 的本地投影
- 本地 roadmap 不再承担独立关系判断

### Phase 4: 统一 PR / issue / closeout 交付规则

**Files**
- Modify: `docs/standards/v2/git-workflow-standard.md`
- Modify: `docs/standards/v2/handoff-governance-standard.md`
- Modify: `skills/vibe-commit/SKILL.md`
- Modify: `skills/vibe-integrate/SKILL.md`
- Modify: `skills/vibe-done/SKILL.md`

**Step 1: 明确 task / PR / issue 归属规则**

- 一个 task 可以关联多个小 issue
- 一个 PR 只关闭它真实完成的 issue
- 大 issue 作为母题和汇总，不直接等价于单个 task 完成

**Step 2: 写清串行 / stacked PR 约束**

- 当 PR 指向 default branch 时，允许用 closing keywords 自动关闭 issue
- 非 default branch 或 stacked PR 中，不依赖 auto-close 做事实判断
- integrate / done 需要明确哪些 issue 已由哪个 merged PR 完成

**Step 3: 写清 handoff 清理义务**

- `vibe-done` 收口时清理 handoff 中已完成、已过时的段落
- 保留必要审计证据，不保留已完成阶段的噪音堆积

**Step 4: 验证**

Run:

```bash
rg -n "close|issue|handoff|stack|PR" docs/standards/v2/git-workflow-standard.md docs/standards/v2/handoff-governance-standard.md skills/vibe-commit/SKILL.md skills/vibe-integrate/SKILL.md skills/vibe-done/SKILL.md
```

Expected:
- 发布层、整合层、收口层对 issue/PR 归属规则一致

### Phase 5: 最后再做性能与补洞

**Files**
- Modify: `lib/roadmap_issue_intake.sh`
- Modify: `lib/roadmap_project_sync.sh`
- Test: `tests/roadmap/*.bats`

**Step 1: 处理 `#122`**

- 在 sync 语义稳定后，再做 intake 去重的预计算优化

**Step 2: 处理 runtime / explainability follow-up**

- `#119`
- `#152`
- `#153`
- `#154`
- `#155`

这些 issue 按各自范围推进，但不再重开数据模型讨论。

## Risks

### Risk 1: 在 Phase 2 前先动 sync，导致用户主链继续被 roadmap mirror 阻塞
- **Impact:** 设计方向正确，但用户体验最痛的点不先解决
- **Mitigation:** 先做 task gate 解耦，再做 projection 重构

### Risk 1.5: 未先完成语义清理就直接推进主计划，导致 `flow/worktree/branch` 与 `repo issue/task issue` 继续混用
- **Impact:** 文档与实现会继续把历史残留当成正式模型，后续清退成本更高
- **Mitigation:** 先执行语义清理前置计划，再进入 GH-157 主计划

### Risk 2: local-first 被误用成第二真源
- **Impact:** 本地又长出一套与 GitHub 并行的关系解释层
- **Mitigation:** `--local` 只做显式例外，并要求 sync_state / remote id 生命周期清晰

### Risk 2.5: 把 `roadmap.json` 留存误解成“长期必须保留的执行真源”
- **Impact:** cache 层重新膨胀成第二套身份模型
- **Mitigation:** 所有文档统一写成 projection / cache / backup，并把是否继续保留留给后续运行证据决定

### Risk 3: 把 parent issue 自动关闭写成核心契约
- **Impact:** 实现依赖不存在或不稳定的 GitHub 能力
- **Mitigation:** 先把 parent issue 只定义成 hierarchy / progress 汇总对象

### Risk 4: 串行 PR 继续混淆“哪个 PR 解决哪个 issue”
- **Impact:** merge 后 closeout 证据继续混乱
- **Mitigation:** 在 Phase 4 单独写清 PR -> issue 归属规则，不把它混进数据模型主体

## Test Strategy

- 合同测试优先于实现：
  - task gate 合同
  - roadmap sync projection 合同
  - PR/issue closeout contract 文档审计
- 每个 Phase 单独收口，不接受“大改一波再一起验证”

## Expected Result

- 设计层：明确 remote-first / local projection 的正式语义
- 执行层：task 可以直接从 issue + spec 起步
- 规划层：roadmap sync 只承担 GitHub Project / issue relations 的 projection
- 交付层：PR / issue / parent issue / handoff 的归属与关闭规则一致
- 治理层：`#157` 成为总 issue，`#158` 成为总设计锚点，其余 issue 变成分阶段实施清单

## Plan Complete Handoff

Plan complete and saved to `docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-plan.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints
