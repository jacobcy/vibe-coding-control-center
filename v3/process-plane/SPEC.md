# Process Plane SPEC (Canonical)

## 1. 定位
Process Plane 负责 provider 路由与 design/plan/execution 过程治理。

## 2. 迁移声明
- 本项目是架构迁移：复用 V2/OpenSpec/Kiro 经验，沉淀 V3 provider 解耦模型。
- V3 迁移阶段仅在 `v3/` 目录改写规范，不改写 V2 原文档。

## 3. Provider 范围
- OpenSpec
- Supervisor（六层结构）
- Kiro
- Manual（降级）

## 4. Router 契约
- `route(task)`
- `start(task, context)`
- `status(provider_ref)`
- `complete(provider_ref)`

## 5. 与控制平面耦合最小化
只输出：`provider`, `provider_ref`, 聚合状态。
不输出 provider 内部阶段细节。

## 6. 边界
- 不重定义控制平面状态机
- 不执行 worktree/tmux 操作

## 7. 本目录规范文件
- `SPEC.md`：本文件（唯一规范入口）
- `PLAN.md`：迁移执行计划
- 其他 md：历史迁移稿，保留不删
