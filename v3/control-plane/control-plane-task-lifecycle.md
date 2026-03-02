# PRD: Control Plane — Cross-Worktree Task Lifecycle

## 1. Overview
将 `vibe` 定位为控制平面：只管理跨 worktree 的任务生命周期和全局状态可见性，不执行 worktree/tmux 实际操作。

## 2. Problem Statement
当前任务管理与会话执行、流程框架语义耦合，导致：
- 状态来源不统一
- provider 切换成本高
- 单会话内难以稳定复盘并行任务现场

## 3. Product Goals
- 建立 provider 无关的任务状态机
- 建立跨 worktree 的统一任务账本
- 降低 `vibe` 对执行细节与流程细节的耦合

## 4. Non-Goals
- 不新增 worktree/tmux 执行命令
- 不管理 design/plan/execution 细节
- 不定义 provider 内部流程步骤

## 5. Primary Users
- 人类维护者（全局任务调度）
- AI agent（状态读写、任务接管）
- 监控脚本（读取统一状态）

## 6. Core Domain Model
- `task_id`
- `title`
- `status` (`todo|in_progress|blocked|done|archived`)
- `owner`
- `provider`
- `provider_ref`
- `worktree_hint`
- `updated_at`

## 7. State Machine
状态迁移规则：
- `todo -> in_progress`
- `in_progress -> blocked|done`
- `blocked -> in_progress|archived`
- `done -> archived`
- 禁止跨级直接跳转（除 `force` 管理操作）

## 8. Command Contract (`vibe task`)
- `task list`: 全局状态视图
- `task add`: 创建任务最小记录
- `task update`: 更新 `status/owner/provider/provider_ref/worktree_hint`
- `task done`: 语义化完成（等价更新状态）
- `task archive`: 归档

## 9. Data Contract & Compatibility
- 读路径：兼容旧字段
- 写路径：仅写最小字段集合
- 冲突策略：`updated_at` 最后写入优先（后续可升级版本向量）

## 10. Observability & Auditability
- 输出统一机器可读 JSON 视图
- 记录最小变更日志（任务状态变化）
- 支持外部监控周期性巡检

## 11. Success Metrics
- provider 切换无需改 task 核心字段
- 单命令可列出所有活跃任务状态
- 多 worktree 状态不再依赖目录命名推断

## 12. Risks
- 旧流程文档仍引用过时状态语义
- 人工绕过命令直接改 registry 导致漂移

## 13. Rollout Plan
- M1：文档冻结与命令契约确认
- M2：schema v2 发布（兼容读）
- M3：迁移旧任务数据

## 14. Open Questions
- 是否需要 `priority` 进入核心字段？
- `force` 迁移权限如何约束？
