---
document_type: audit
title: Shell Skill Boundary Audit
status: approved
scope: shell-skill-boundary
author: Codex GPT-5
created: 2026-03-08
last_updated: 2026-03-10
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

本审计使用 [shell-capability-design.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/shell-capability-design.md) 中的审查原则，并将 [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md) 作为命令语义真源。

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

### 2.2 Resolved In Text Layer: `task` 已具备 repo issue / roadmap 关联入口

当前 [task_actions.sh](/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection/lib/task_actions.sh) 已支持：

- `task add --issue ... --roadmap-item ...`
- `task update --issue ... --roadmap-item ...`

这意味着 “repo issue / roadmap item -> local task execution record” 的基础关联入口已经存在。

判定：

- `Contract Available`
- `Needs Terminology Tightening`

期望：

- help 与 skill 文案统一使用 `repo issue`
- 明确本地 task 是 execution record，而不是 `type=task` 的规划对象

### 2.3 Blocking: `roadmap current` 不能被解释为分支当前态

依据 [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md)，`roadmap.current` 属于规划窗口状态，而分支当前焦点属于 `flow` / task runtime。

如果 shell 或 skill 将 `roadmap.current` 误解释为分支当前态，就会导致：

- 多分支开发冲突
- 共享规划状态与运行时现场混淆
- 错误地让 `roadmap` 承担 `flow` 语义

判定：

- `Semantic Boundary`

期望：

- 按 [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md) 执行，不在 shell 或 skill 中重写这套语义

### 2.4 Blocking: `repo issue`、`task`、`flow` 的业务概念必须明确区分

依据 [command-standard.md](/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection/docs/standards/command-standard.md)，`repo issue`、`roadmap item`、`task`、`flow` 的职责与关系已在命令标准中定义。

如果 shell 或 skill 混用这些概念，就会产生两类问题：

- Shell 越权替 skill 做任务拆分决策
- skill 误以为调用单个 shell 命令就能完成业务逻辑

判定：

- `Concept Boundary`

期望：

- 业务概念统一引用 [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md)
- 文件字段与关系统一引用数据模型标准

### 2.5 High: `registry.json` 标准与当前 task 写入字段不一致

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

### 2.6 High: `roadmap classify` 越权执行“分类 + 新增实体”

当前 [roadmap_write.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/roadmap_write.sh#L73) 到 [roadmap_write.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/roadmap_write.sh#L97) 中，`vibe roadmap classify` 在找不到 roadmap item 时会自动新增 item。

这使得 `classify` 同时承担：

- 查找
- 实体创建
- 状态分类

判定：

- `Shell Overreach`

期望：

- `classify` 只负责已有 item 的状态变更
- 新增 item 必须显式通过 `roadmap add` 或 `roadmap sync`

### 2.7 Resolved In Text Layer: 入口 workflow 文案已基本对齐

[vibe-new-feature.md](/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection/.agent/workflows/vibe-new-feature.md)、[vibe-new-flow.md](/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection/.agent/workflows/vibe-new-flow.md)、[vibe-issue.md](/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection/.agent/workflows/vibe-issue.md) 已明确写了：

- 必须通过 shell 命令写共享真源
- 不得直接手工编辑 JSON

这与本审计目标一致。

问题已不再是 workflow 文案，而是 shell 对 GitHub Project item / milestone 的能力仍不完整。

判定：

- `Contract Accurate`
- `Blocked By Shell Gap`

### 2.8 Resolved In Text Layer: `vibe-roadmap` skill 已切到 GitHub-first 语义

[vibe-roadmap/SKILL.md](/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection/skills/vibe-roadmap/SKILL.md) 已明确：

- roadmap item 是 mirrored GitHub Project item
- milestone 是规划窗口锚点
- task 是 execution record

判定：

- `Contract Accurate`

### 2.9 Medium: `vibe-task` 与 `vibe-save` skill 文案整体正确

[vibe-task/SKILL.md](/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection/skills/vibe-task/SKILL.md) 已明确：

- Shell 提供原子操作
- Skill 负责语义分析和决策

[vibe-save/SKILL.md](/Users/jacobcy/src/vibe-center/wt-fix-pr-base-selection/skills/vibe-save/SKILL.md) 也明确禁止直接编辑底层真源。

判定：

- `Contract Accurate`

## 3. Audit Summary

当前边界状态可以概括为：

- 标准原则以前写得不够显式，现在已补强
- `roadmap.current` 与 branch current 的语义边界现已明确
- `repo issue`、`task`、`flow` 的关系边界现已明确
- 大部分 skill 文案已经接受“shell 是工具，不是业务执行者”这一原则
- 当前主要问题不在入口文案，而在 Shell 尚未真正对齐 GitHub Project item / milestone 能力
- `roadmap sync` 相关实现仍暴露出“repo issue 镜像”和“GitHub Project item 镜像”未分离的风险

## 4. Required Follow-Up

后续能力补图必须优先完成：

1. 将 `flow new` 收紧为纯现场创建
2. 将 `roadmap sync` 从 “repo issue -> local item” 提升为真正的 `GitHub Project item <-> roadmap item` 对齐
3. 让 `milestone` 成为正式的版本/阶段窗口同步锚点，而不只停留在标准文本
4. 增加从已有 PR / commits 回填 task execution record 的能力
5. 明确本地 task 与 GitHub `type=task` roadmap item 的桥接模型

在以上五项完成前，系统只能部分支持 GitHub-first 工作流：

- `repo issue -> roadmap item -> task -> flow`

但还不能说已经完全对齐 GitHub Project / milestone / task backfill 语义。
