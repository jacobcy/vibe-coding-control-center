# V3 Workspace

V3 采用“总 PRD + 三个独立子项目”模式：

- `MASTER-PRD.md`：总目标、跨项目约束、协作协议
- `control-plane/`：控制平面（任务生命周期）
- `execution-plane/`：执行平面（worktree/tmux/aliases）
- `process-plane/`：流程平面（provider 路由）

每个子目录固定文件：
- `SPEC.md`：该子项目唯一规范入口（canonical）
- `PLAN.md`：迁移执行计划（基于 SPEC）
- 其他同目录文档：历史草稿/迁移稿，保留不删

## 设计原则

1. 每个子项目独立演进，不混改其他子项目目录。
2. 每个子项目必须有自己的 PRD 与修改边界文件。
3. 跨项目协作通过接口契约完成，不通过“直接改对方代码”完成。
4. V3 当前阶段只在 `v3/` 目录修改；允许从 V2 拷贝内容，但不直接在 V2 文档上改写。
