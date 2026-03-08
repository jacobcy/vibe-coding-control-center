---
document_type: audit
title: Shell Skill Boundary Audit
status: approved
scope: shell-skill-boundary
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-03-08
related_docs:
  - docs/standards/command-standard.md
  - docs/standards/shell-capability-design.md
  - docs/standards/skill-standard.md
---

# Shell Skill Boundary Audit

本文档记录当前 Shell 与 Skill 边界的审计基线，用于检查两类问题：

- Shell 是否越权执行了应由 skill 负责的业务逻辑
- Skills / workflows 是否准确描述了 Shell 只是工具，而不是业务执行者

## 1. Audit Questions

审计时统一使用以下问题：

1. Shell 是否提供了足够的原子能力让 skill 完成工作？
2. Shell 是否跨越职责边界，执行了 workflow logic？
3. Skill 是否暗示“调用 shell 命令即可完成业务逻辑”？
4. Skill 是否被诱导绕过 Shell 直接触碰共享状态？

## 2. Findings

### 2.1 Blocking: `flow new` 越权创建 task

当前 [flow.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/flow.sh#L19) 到 [flow.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/flow.sh#L37) 中，`vibe flow new` 会：

- 生成 task id
- 注册 task
- 创建 worktree
- 绑定 task

这已经不是“创建现场”，而是在执行完整 workflow 片段。

判定：

- `Shell Overreach`

期望：

- `flow new` 只创建现场
- 任务创建与关联由 `task` 命令提供原子能力
- skill 负责决定先建 task 还是先开 flow

### 2.2 Blocking: `task` 缺少 issue / roadmap 关联原子能力

当前 [task_actions.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/task_actions.sh#L50) 到 [task_actions.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/task_actions.sh#L71) 中，`vibe task add` 只能创建最小 task 记录。

当前 [task_actions.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/task_actions.sh#L8) 到 [task_actions.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/task_actions.sh#L18) 中，`vibe task update` 也不支持：

- `--issue-ref`
- `--roadmap-item`

这意味着 skill 若想把 `#59` 拆成多个本地 task 并建立统一关联，Shell 目前没有足够能力。

判定：

- `Capability Gap`

期望：

- `task add --issue-ref ... --roadmap-item ...`
- `task update --issue-ref ... --roadmap-item ...`

### 2.3 High: `registry.json` 标准与当前 task 写入字段不一致

标准要求 task 应包含：

- `source_type`
- `source_refs`
- `roadmap_item_ids`
- `issue_refs`
- `related_task_ids`

见 [registry-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/registry-json-standard.md#L66) 到 [registry-json-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/registry-json-standard.md#L109)。

但当前 [task_actions.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/task_actions.sh#L68) 和 [task_write.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/task_write.sh#L65) 只写最小字段，尚未对齐标准。

判定：

- `Capability Gap`

### 2.4 Medium: `vibe-new` workflow 文案基本正确，但依赖的 Shell 合同尚未落地

[vibe-new.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/.agent/workflows/vibe-new.md#L15) 到 [vibe-new.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/.agent/workflows/vibe-new.md#L22) 明确写了：

- 必须通过 shell 命令写共享真源
- 不得直接手工编辑 JSON

这与本审计目标一致。

问题不在 workflow 文案，而在其依赖的 Shell 方法还不完整。

判定：

- `Contract Accurate`
- `Blocked By Shell Gap`

### 2.5 Medium: `vibe-roadmap` skill 文案与目标原则一致

[vibe-roadmap/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-roadmap/SKILL.md#L8) 到 [vibe-roadmap/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-roadmap/SKILL.md#L28) 已明确：

- CLI 负责读写
- skill 负责调度决策
- 不得直接改底层数据

判定：

- `Contract Accurate`

### 2.6 Medium: `vibe-task` 与 `vibe-save` skill 文案整体正确

[vibe-task/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-task/SKILL.md#L825) 到 [vibe-task/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-task/SKILL.md#L839) 已明确：

- Shell 提供原子操作
- Skill 负责语义分析和决策

[vibe-save/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-save/SKILL.md#L140) 也明确禁止直接编辑底层真源。

判定：

- `Contract Accurate`

## 3. Audit Summary

当前边界状态可以概括为：

- 标准原则以前写得不够显式，现在已补强
- 大部分 skill 文案已经接受“shell 是工具，不是业务执行者”这一原则
- 当前主要问题不在 skill，而在 Shell 缺少足够的原子能力，同时某些命令越权编排

## 4. Required Follow-Up

后续 Shell 收敛必须优先完成：

1. 将 `flow new` 收紧为纯现场创建
2. 为 `task add` / `task update` 增加 issue / roadmap 关联原子能力
3. 让 skill 能通过公开命令完成 task 拆分与绑定，而无需触碰数据源

在以上三项完成前，系统只能部分支持：

- `roadmap -> 拆多个 task -> flow 绑定多个 task`

但还不能说完全符合标准工作流。
