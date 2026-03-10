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

- Shell 是否越权执行了应由 skill 负责的业务判断
- Skills / workflows 是否准确描述了 Shell 是围绕共享真源的能力层，而不是业务判断者

## 1. Audit Questions

本审计使用 [shell-capability-design.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/shell-capability-design.md) 中的审查原则，并将 [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md) 作为命令语义真源。

审计时统一使用以下问题：

1. Shell 是否提供了足够的共享真源相关能力让 skill 完成工作，而不必自己拼接高成本机械步骤？
2. Shell 是否替 skill 做了归属、拆分、优先级、下一步等业务判断？
3. Shell 的 `git` / `gh` / worktree 副作用是否都服务于共享真源同步或单一现场落地？
4. Skill 是否暗示“调用 shell 命令即可自动完成业务判断”？
5. Skill 是否被诱导绕过 Shell 直接触碰共享状态？

## 2. Findings

### 2.1 Medium: `flow new` 的边界不应按“是否同时碰多个对象”来判断

当前 [flow.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/flow.sh#L19) 到 [flow.sh](/Users/jacobcy/src/vibe-center/wt-claude-refactor/lib/flow.sh#L37) 中，`vibe flow new` 会：

- 生成 task id
- 注册 task
- 创建 worktree
- 让 flow 对应 task

仅仅因为一个命令同时触碰 task / flow / worktree，并不能自动判定为越权。

如果这些动作都服务于同一个共享真源同步目标，且不替 skill 决定任务拆分、issue/roadmap 归属、优先级和 next step，那么它仍可能是可接受的中等粒度 Shell 能力。

真正需要审计的是：`flow new` 是否在没有显式上层判断的情况下，替 skill 做了业务归属决定。

判定：

- `Needs Clarification`

期望：

- 不再使用“只要同时创建 task 和现场就一定越界”这一过度绝对化判据
- 审查重点改为：它是否替 skill 决定了本轮交付的业务语义
- 若只是围绕当前单一 flow 建立共享事实与现场落地，则可以保留为 Shell 能力

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

### 2.4 Blocking: `issue`、`task`、`flow` 的业务概念必须明确区分

依据 [command-standard.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/docs/standards/command-standard.md)，`issue`、`roadmap item`、`task`、`flow` 的职责与关系已在命令标准中定义。

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

### 2.7 Medium: `vibe-new` workflow 文案基本正确，但依赖的 Shell 合同尚未落地

[vibe-new.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/.agent/workflows/vibe-new.md#L15) 到 [vibe-new.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/.agent/workflows/vibe-new.md#L22) 明确写了：

- 必须通过 shell 命令写共享真源
- 不得直接手工编辑 JSON

这与本审计目标一致。

问题不在 workflow 文案，而在其依赖的 Shell 方法还不完整。

判定：

- `Contract Accurate`
- `Blocked By Shell Gap`

### 2.8 Medium: `vibe-roadmap` skill 文案方向正确，但有一处能力描述超前

[vibe-roadmap/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-roadmap/SKILL.md#L8) 到 [vibe-roadmap/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-roadmap/SKILL.md#L28) 已明确：

- CLI 负责读写
- skill 负责调度决策
- 不得直接改底层数据

但 [vibe-roadmap/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-roadmap/SKILL.md#L79) 到 [vibe-roadmap/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-roadmap/SKILL.md#L86) 仍写有“从当前版本 backlog 中分配最高优先级任务”。

这句话的问题是：

- 它容易让 agent 误以为 `roadmap.current` 等于 branch 当前任务池
- 它也容易让 agent 误以为现有 shell 已能直接完成 roadmap -> task 分配

判定：

- `Contract Mostly Accurate`
- `Needs Clarification`

### 2.9 Medium: `vibe-task` 与 `vibe-save` skill 文案整体正确

[vibe-task/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-task/SKILL.md#L825) 到 [vibe-task/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-task/SKILL.md#L839) 已明确：

- Shell 提供原子操作
- Skill 负责语义分析和决策

[vibe-save/SKILL.md](/Users/jacobcy/src/vibe-center/wt-claude-refactor/skills/vibe-save/SKILL.md#L140) 也明确禁止直接编辑底层真源。

判定：

- `Contract Accurate`

## 3. Audit Summary

当前边界状态可以概括为：

- 标准原则以前写得不够显式，现在已补强
- Shell 可以调用 `git` / `gh` / worktree，但这些副作用必须服务于共享真源与单一现场同步
- `roadmap.current` 与 branch current 的语义边界现已明确
- `issue`、`task`、`flow` 的关系边界现已明确
- 大部分 skill 文案已经接受“shell 是能力层，不是业务判断者”这一原则
- 当前主要问题不在 shell 会不会调用 `git` / `gh`，而在它是否替 skill 做了语义判断，以及当前原子能力是否足够
- `roadmap` 相关实现已经暴露出“共享规划状态”和“分支运行时状态”混用风险

## 4. Required Follow-Up

后续 Shell 收敛必须优先完成：

1. 明确 `flow new` 的合法边界是“围绕当前单一 flow 的共享真源与现场同步”，而不是简单要求它退化为纯现场创建
2. 为 `task add` / `task update` 增加 issue / roadmap 关联原子能力
3. 修正 `roadmap classify`，禁止隐式新增 roadmap item
4. 收紧 `vibe-roadmap` skill 对 `roadmap.current` 与 backlog 分配的描述
5. 让 skill 能通过公开命令完成 task 拆分与绑定，而无需触碰数据源

在以上五项完成前，系统只能部分支持：

- `roadmap -> 拆多个 task -> flow 绑定多个 task`

但还不能说完全符合标准工作流。
