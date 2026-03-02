# PRD: Process Plane Project

## 1. 项目定义

Process Plane 负责 design/plan/execution 流程编排与 provider 路由，包含 OpenSpec、Supervisor（六层）、Kiro。

## 2. 目标

- provider 解耦接入
- 路由策略可配置
- provider 内部流程独立演进

## 3. 非目标

- 不重定义控制平面状态机
- 不直接执行 worktree/tmux 命令

## 4. Provider Router 接口

- `route(task)`
- `start(task, context)`
- `status(provider_ref)`
- `complete(provider_ref)`

## 5. Supervisor 六层模型（内部）

1. Intake
2. Scoping
3. Design
4. Plan
5. Execution
6. Audit/Close

注：六层仅在流程平面内部生效，不映射为控制平面核心状态。

## 6. 接口输入输出

输入：任务上下文 + 路由策略。  
输出：`provider`, `provider_ref`, 聚合状态。

## 7. 验收标准

- 新增 provider 不改控制平面 schema
- provider 不可用时可降级 `manual`
