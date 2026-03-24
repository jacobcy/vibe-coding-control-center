---
document_type: plan
title: GH-157 Semantic Cleanup Expansion Plan
status: proposed
author: GPT-5 Codex
created: 2026-03-13
last_updated: 2026-03-13
related_docs:
  - docs/plans/2026-03-13-gh-157-semantic-cleanup-prerequisite-plan.md
  - docs/plans/2026-03-13-gh-157-worktrees-json-retirement-plan.md
  - docs/plans/2026-03-13-gh-157-remote-first-roadmap-governance-plan.md
  - docs/standards/glossary.md
  - docs/standards/v3/data-model-standard.md
  - docs/standards/v3/command-standard.md
  - docs/standards/v3/registry-json-standard.md
related_issues:
  - gh-157
  - gh-158
  - gh-152
---

# GH-157 Semantic Cleanup Expansion Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在完成语义清理前置 plan 之后，把新语义扩散到会直接影响 agent 决策的标准、skills 与 workflows，并再做一轮残留审计，确保 `worktree/flow/branch`、`roadmap cache`、`task issue` 不会在执行入口重新走样。

**Architecture:** 先修执行入口的高风险漂移点，再处理仍会被误当现行标准的历史设计文档，随后把 `task issue` 与 `worktrees.json` 的兼容定位扩散到关键 skill/workflow，最后用一轮全文 `rg` 审计收口。整个 plan 只处理文档与说明层，不改 shell 实现。

**Tech Stack:** Markdown, Zsh, ripgrep

---

## Goal / Non-goals

**Goal**
- 修掉会直接影响 agent 恢复/路由/继续工作的旧语义文案
- 明确哪些历史设计文档仍可保留，哪些必须降级或改口
- 把 `task issue` 的正式语义扩散到执行入口说明
- 把 `worktrees.json` 的“兼容期 cache / audit hint”定位扩散到关键文档

**Non-goals**
- 本计划不修改 shell 代码
- 本计划不实现 `worktrees.json` 清退
- 本计划不新增新的共享状态 schema
- 本计划不重写所有历史 plans，只处理仍会被当前执行入口消费或误读的文档

## Review Baseline

本轮扩散以以下正式语义为准：

- `flow` 是 branch 锚定的逻辑交付现场，不等于 `worktree`
- `worktree` 是 Git 物理目录容器，只提供物理承载与兼容期 hint
- `roadmap.json` 当前只按 mirror / cache / projection / backup 理解
- `task issue` 是 `repo issue` 的 execution role，不是新的平行实体

## P0 Findings To Fix First

### 1. `/vibe-continue` 恢复顺序仍把 `worktrees.json` 置于第一真源

当前 `skills/vibe-continue/SKILL.md` 仍写成：

- 先读 `worktrees.json`
- 再读 `registry.json`
- 并优先从 `worktrees.json` 识别当前 task

这与 branch-first / registry-first 语义冲突，应优先修正。

### 2. `vibe-engine-design.md` 仍放在 standards 目录且正文保留强历史叙事

该文档虽然有边界补充，但正文仍会被读成现行架构标准。若继续保留在 `docs/standards/`，必须明确它是历史设计/背景材料；否则应迁移到 references 或 archive 类位置。

### 3. `task issue` 已进入标准，但还未充分扩散到执行入口文案

目前 glossary / command / registry 已经有 `task issue`，但关键 skill/workflow 对“主闭环 issue”还缺少明确落点，容易导致执行时继续把任意 `issue_ref` 当主 issue。

## Task 1: 修执行入口的高风险漂移

**Files:**
- Modify: `skills/vibe-continue/SKILL.md`
- Modify: `skills/vibe-start/SKILL.md`
- Modify: `skills/vibe-check/SKILL.md`
- Modify: `.agent/workflows/vibe:start.md`
- Modify: `.agent/workflows/vibe:task.md`

**Step 1: 调整 `/vibe-continue` 恢复顺序**

- 改成先看 `git` 现场与 `registry.json`
- `worktrees.json` 只能作为兼容期辅助线索
- 若存在 `primary_issue_ref`，明确它就是 `task issue` 的显式落点

**Step 2: 补齐执行入口的 issue 语义**

- `vibe-start` 要明确：`issue_refs` 是候选来源，`primary_issue_ref` 才是 task 的主闭环 issue
- `vibe-check` / `vibe:task` 只在 runtime / audit 语义下提 `worktree`
- 避免把 `worktree` 写成“现场主体”

**Step 3: 验证**

Run:

```bash
rg -n "worktrees\\.json|primary_issue_ref|task issue|repo issue -> flow|进入哪个 worktree|当前 worktree 绑定的 task" skills .agent/workflows
```

Expected:
- 关键入口不再把 `worktrees.json` 写成第一真源
- `task issue` 或 `primary_issue_ref` 的落点已可见
- 没有把 `worktree` 写成 runtime 主语的高风险措辞

## Task 2: 处理仍会被误读成现行标准的历史设计文档

**Files:**
- Modify: `docs/standards/v3/vibe-engine-design.md`
- Review: `docs/plans/2026-03-11-flow-worktree-semantic-confusion-analysis.md`

**Step 1: 决定 `vibe-engine-design.md` 的身份**

二选一：

1. 保留在 `docs/standards/`，但在开头明确标注“历史架构设计背景，不作为现行标准真源”
2. 迁移到 `docs/references/` 或等价位置，并在原位置留迁移说明

推荐优先选项 2，因为它当前的正文不是标准体裁。

**Step 2: 清理误导性现行口吻**

- 不再把文中的 gate / engine / stage 直接表述成现行必经标准
- 明确它是历史设计蓝图、背景思考或已部分过时的架构设想

**Step 3: 验证**

Run:

```bash
rg -n "已按现行标准收敛语义|统一工作流编排器|Stage 1|Stage 2|Execution Gate|Review Gate" docs/standards docs/references
```

Expected:
- 不会再出现一份“放在 standards 里但正文像历史蓝图”的高混淆文档

## Task 3: 扩散 `task issue` 与 roadmap cache 语义

**Files:**
- Modify: `docs/standards/v3/skill-standard.md`
- Modify: `docs/standards/v3/skill-trigger-standard.md`
- Modify: `skills/vibe-commit/SKILL.md`
- Modify: `skills/vibe-integrate/SKILL.md`
- Modify: `skills/vibe-done/SKILL.md`

**Step 1: 补齐主闭环 issue 口径**

- 说明一个 task 可以有多个 `issue_refs`
- 但只有 `primary_issue_ref` 对应的那个 `repo issue` 才是 `task issue`
- PR / integrate / done 语义优先围绕主闭环 issue 判断

**Step 2: 补齐 roadmap cache 口径**

- 提醒 roadmap 只是 planning projection / cache
- 不要再把 roadmap mirror 缺失写成 execution 不可启动的根因

**Step 3: 验证**

Run:

```bash
rg -n "primary_issue_ref|task issue|issue_refs|roadmap.*cache|roadmap.*projection|execution gate" docs/standards/v3/skill-standard.md docs/standards/v3/skill-trigger-standard.md skills/vibe-commit/SKILL.md skills/vibe-integrate/SKILL.md skills/vibe-done/SKILL.md
```

Expected:
- 交付入口文案能区分 `issue_refs` 与 `task issue`
- roadmap 不再被暗示为 execution gate

## Task 4: 做一轮残留审计并列出后续不立即修的历史文档

**Files:**
- Review: `docs/standards/**/*.md`
- Review: `skills/**/*.md`
- Review: `.agent/workflows/*.md`
- Create: `docs/plans/2026-03-13-gh-157-semantic-cleanup-audit-report.md`

**Step 1: 全文扫描高风险残留**

重点搜：

- 把 `worktree` 写成 runtime 主语
- 把 `worktrees.json` 写成第一真源
- 把 roadmap 写成 execution gate
- 把任意 `issue_ref` 默认写成 task 的主 issue

**Step 2: 分类**

- `P0`：会直接影响当前 agent 行为，必须立即修
- `P1`：文档仍误导，但不直接影响执行入口
- `P2`：历史分析/归档材料，可留待后续统一整理

**Step 3: 产出审计报告**

- 列出发现项
- 指出是否已修
- 标出可延期处理的历史残留

**Step 4: 验证**

Run:

```bash
rg -n "worktrees\\.json|进入哪个 worktree|继续当前 worktree 绑定的 task|execution gate|task issue|primary_issue_ref|现场态真源" docs/standards skills .agent/workflows docs/plans
```

Expected:
- P0 残留已收敛
- 剩余命中大多为已明确标注的历史分析或迁移说明

## Exit Criteria

- `skills/vibe-continue/SKILL.md` 不再把 `worktrees.json` 作为恢复第一真源
- `vibe-engine-design.md` 的身份不再模糊
- 关键执行入口已能表达 `task issue` / `primary_issue_ref`
- 完成一份新的语义残留审计报告，供后续收尾
