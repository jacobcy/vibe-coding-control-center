# PRD: V3 Multi-Agent Isolated Architecture

## 1. 背景与目标

V3 的核心目标：在多 agent 并行开发中，保证“认知独立、代码边界独立、交付可组合”。

为此采用：
- 一个总 PRD（本文件）
- 三个独立子项目 PRD（控制/执行/流程）
- 每个子项目独立目录、独立修改边界

## 0.1 迁移原则（关键）

本次为**架构迁移**，不是完全改写：
- 允许从 V2 代码与文档中复制可复用逻辑/片段
- V3 阶段只在 `v3/` 目录内产出与改写规范文件
- 不删除 V2 计划/文档文件，仅在 V3 建立新的 canonical 规范

## 2. 总体架构

- **控制平面（Control Plane）**：`vibe` 跨 worktree 任务生命周期管理
- **执行平面（Execution Plane）**：`aliases` 驱动 worktree/tmux 执行与会话恢复
- **流程平面（Process Plane）**：OpenSpec / Supervisor / Kiro provider 路由与治理

## 3. Agent 视野隔离规则

每个 agent 只看：
1. 本子项目目录下文档
2. 总 PRD 的接口契约章节
3. 自己被授权的代码路径

禁止：
- 未经总 PRD 协议直接修改其他子项目范围
- 在本子项目 PRD 里定义跨项目内部实现细节

## 4. 跨项目接口契约（最小）

### 4.1 Control -> Execution
输出执行意图：`task_id`, `worktree_hint`, `session_hint`。

### 4.2 Execution -> Control
回写执行结果：`resolved_worktree`, `resolved_session`, `timestamp`, `executor`。

### 4.3 Control -> Process
写入：`provider`, `provider_ref`, `status`。

### 4.4 Process -> Control
回写：`provider_state` 的聚合结果（不暴露 provider 内部步骤）。

## 5. 状态统一原则

控制平面状态机固定：
`todo -> in_progress -> blocked -> done -> archived`

流程平面内部状态不得覆盖控制平面核心状态。

## 6. 目录结构与所有权

- `v3/control-plane/*`：Control Agent owner
- `v3/execution-plane/*`：Execution Agent owner
- `v3/process-plane/*`：Process Agent owner
- `v3/MASTER-PRD.md`：架构 owner + 各 owner 联合评审

每个子目录以 `SPEC.md` 作为规范入口，以 `PLAN.md` 作为迁移执行计划入口。

## 6.1 命名与命令规范（V3 Canonical）

为解决 V2 命名混乱，V3 统一采用：

- 资源名用单数：`vibe task`（不是 `vibe tasks`）
- 创建动作用 `create`：`vibe task create`（不是 `vibe task add`）
- 入口命令统一为 `vibe flow start`（不是 `vibe new`）

兼容策略（迁移期）：
- `vibe task add` 作为过渡别名，最终废弃
- `vibe new` 作为过渡别名，最终废弃
- 所有新文档只写 canonical 命令

## 7. 交付与验收

验收必须同时满足：
1. 三个子项目 PRD 完整且互不冲突
2. 每个子项目有明确 allowed paths
3. 任一 agent 可以只凭本项目 PRD + 总 PRD 接口段开始工作
4. 没有“跨目录隐式依赖”描述

## 8. 风险

- 风险 1：边界定义了但实现阶段仍交叉改动
- 风险 2：流程平面语义渗透回控制平面
- 风险 3：执行平面临时脚本未纳入接口契约

## 9. 里程碑

- M1：完成总 PRD + 三个子项目 PRD（当前阶段）
- M2：各子项目产出实现计划（仅本边界）
- M3：按接口契约联调
