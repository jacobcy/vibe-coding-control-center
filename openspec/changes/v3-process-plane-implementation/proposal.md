# Proposal: V3 Process Plane Implementation

## Why

Vibe Center 当前 V2 架构中，provider（OpenSpec、Supervisor、Kiro）耦合度高，路由逻辑分散，难以独立演进和扩展。为实现多 agent 并行开发中的"认知独立、代码边界独立、交付可组合"目标，需要建立统一的 provider 路由架构，将 provider 接入、路由策略、降级机制标准化。

现在实现此架构可以：
1. 支持新增 provider 不影响控制平面 schema
2. provider 不可用时自动降级到 manual 模式
3. 各 provider 内部流程独立演进，不渗透到控制平面

## What Changes

### 新增能力
- **Provider Router 架构**：统一的 provider 路由、启动、状态查询、完成接口
- **路由策略引擎**：基于任务类型、风险等级、人工策略、资源配置的智能路由
- **降级机制**：provider 不可用时自动降级到 manual 模式，保证系统可用性
- **Provider Adapter 模板**：标准化的 provider 接入规范，支持快速集成新 provider
- **Supervisor 六层模型**：作为流程平面内部标准流程（Intake → Scoping → Design → Plan → Execution → Audit/Close）

### 修改范围
- 仅在 `v3/process-plane/` 目录内实现
- 不修改控制平面状态机
- 不直接执行 worktree/tmux 命令（由执行平面负责）

### 跨平面接口契约
- **Control → Process**: 写入 `provider`, `provider_ref`, `status`
- **Process → Control**: 回写 `provider_state` 聚合结果（不暴露 provider 内部步骤）

## Capabilities

### New Capabilities

- **provider-router**: Provider 路由与生命周期管理，包括 route/start/status/complete 接口
- **routing-strategy**: 基于任务类型、风险、资源配置的智能路由策略引擎
- **provider-fallback**: Provider 降级机制，支持自动降级到 manual 模式
- **supervisor-flow**: Supervisor 六层流程模型（流程平面内部标准）
- **provider-adapter**: Provider 接入模板与规范

### Modified Capabilities

（无 - 这是新增能力，不修改现有 spec-level 行为）

## Impact

### 受影响的代码路径
- `v3/process-plane/*` - 新增实现代码
- 不影响 `lib/`、`bin/` 等 V2 代码（迁移阶段只在 v3/ 目录）

### 依赖关系
- 依赖控制平面提供的任务上下文
- 依赖执行平面提供的 worktree/tmux 能力（通过接口契约）
- 不直接依赖具体 provider 实现，通过 adapter 模式解耦

### 系统影响
- 架构层面：引入 provider router 中间层，解耦控制平面与具体 provider
- 运维层面：provider 可独立升级、降级，不影响系统整体可用性
- 开发层面：新增 provider 只需实现 adapter 接口，无需修改核心路由逻辑

### 迁移影响
- V3 阶段仅在 `v3/` 目录产出，不删除 V2 文档
- 允许从 V2 复制可复用逻辑/片段到 V3
- V3 规范建立后，V2 逐步废弃
