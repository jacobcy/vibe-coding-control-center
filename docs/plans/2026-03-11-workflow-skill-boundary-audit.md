---
document_type: plan
title: workflow skill boundary audit
status: proposed
author: Codex GPT-5
created: 2026-03-11
related_docs:
  - .agent/README.md
  - docs/standards/v2/skill-standard.md
  - .agent/workflows/vibe-new.md
  - .agent/workflows/vibe-start.md
  - .agent/workflows/vibe-commit.md
  - skills/vibe-commit/SKILL.md
  - skills/vibe-task/SKILL.md
  - skills/vibe-check/SKILL.md
  - skills/vibe-save/SKILL.md
  - skills/vibe-issue/SKILL.md
---

# Goal

审计 `.agent/workflows/` 与 `skills/` 的职责边界，判断当前设计是否满足“workflow 只负责流程编排，skill 负责具体业务逻辑”。

# Non-Goals

- 不在本轮直接重写 workflow 或 skill
- 不修改 shell 能力层命令

# Findings

## 1. 薄路由模式在 `vibe-task` / `vibe-check` / `vibe-save` / `vibe-issue` 基本成立

- 对应 workflow 主要承担入口说明、调用 skill、强调 shell/skill 边界。
- 具体业务逻辑主要在 `skills/*/SKILL.md`。
- 这组设计方向是对的。

## 2. `vibe-new` / `vibe-start` 已明显越过“只负责流程”的边界

- `.agent/workflows/vibe-new.md` 内含大量具体业务规则：
  - handoff intake 语义
  - roadmap/task/plan 绑定规则
  - worktree/flow 约束
  - Gate 细化与阻塞逻辑
- `.agent/workflows/vibe-start.md` 内含大量执行策略：
  - task 选择顺序
  - auto 模式跳转
  - blocker 分类
  - handoff 回写要求
- 但仓库中不存在 `skills/vibe-new/SKILL.md`、`skills/vibe-start/SKILL.md`，导致 workflow 自身承担了本应下沉到 skill 的业务逻辑。

## 3. `vibe-commit` 存在 workflow 与 skill 双写逻辑

- `.agent/workflows/vibe-commit.md` 不只是薄委托，已经写入较完整的提交流程和分支策略。
- `skills/vibe-commit/SKILL.md` 也独立维护一套完整逻辑。
- 当前属于“双真源风险”：
  - 流程编排在 workflow 里
  - 业务判断在 skill 里
  - 但两边都写得很实，后续容易漂移

## 4. `.agent/README.md` 已明显落后于当前真实结构

- 仍提到不存在的 `review-code.md` / `review-docs.md`
- 仍提到过时的 `vibe flow sync`
- 没有准确反映“workflow 作为入口、skill 作为业务逻辑载体”的现状

# Design Judgment

当前设计不是完全错误，但已经分成两种模式：

1. 健康模式
- workflow = 薄入口 / 委托层
- skill = 业务逻辑与操作纪律

2. 失衡模式
- workflow = 入口 + 大量业务规则
- skill 缺失，或 workflow/skill 双写

目前最需要收敛的是第二类，尤其是：

- `vibe-new`
- `vibe-start`
- `vibe-commit`

# Recommended Direction

## A. workflow 固定收缩为三类内容

- 触发语义
- 入口流程顺序
- 委托到哪个 skill / shell 能力

不应再在 workflow 内展开完整业务判断树。

## B. skill 固定承载三类内容

- 具体业务判断
- shell 调用顺序与边界
- blocker 处理与结果输出格式

## C. 对现有入口的收敛建议

1. `vibe-new`
- 补 `skills/vibe-new/SKILL.md`
- 把 handoff intake、roadmap/task/plan 绑定规则下沉到 skill
- workflow 只保留入口、Gate 顺序、HARD STOP

2. `vibe-start`
- 补 `skills/vibe-start/SKILL.md`
- 把 auto fallback、task 选择、blocker 分类下沉到 skill
- workflow 只保留“执行入口 + 必须按 plan”

3. `vibe-commit`
- 选一个真源
- 建议 workflow 薄化，skill 保留完整逻辑

4. `.agent/README.md`
- 更新为当前真实目录与入口关系
- 去掉过时命令与不存在的 workflow 链接

# Test / Verification

```bash
find .agent/workflows -maxdepth 1 -type f | sort
find skills -maxdepth 2 -name 'SKILL.md' | sort
```

人工核对：

- `vibe-task` / `vibe-check` / `vibe-save` / `vibe-issue` 为薄路由
- `vibe-new` / `vibe-start` 无对应 skill
- `vibe-commit` workflow 与 skill 双写

# Change Summary

- Added: 1 analysis doc
- Approximate lines: 100-140
