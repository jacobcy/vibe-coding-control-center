# Plan v5: 四层模块重构 — server / runtime / orchestra / manager

## TL;DR

将当前 `server/` + `orchestra/` + `manager/` + `dispatcher/` 整理为四层模块：
- **server** — HTTP/webhook 入口
- **runtime** — 事件循环 + 执行引擎 + 故障保护（合并 dispatcher/ + heartbeat + event_bus）
- **orchestra** — 编排策略 + 治理 + Triage（退化为 assignee 驱动，state label 为只读镜像）
- **manager** — 现场管理（Flow/Worktree 协同 + Queue 准入）

## 架构演进现状 (2026-04-02)

### 1. 模块化状态
- `src/vibe3/runtime/`：**已创建**。包含 `heartbeat.py`, `event_bus.py`, `executor.py`, `circuit_breaker.py`。
- `src/vibe3/dispatcher/`：**已删除**。所有核心逻辑已并入 runtime。
- `src/vibe3/orchestra/`：**已精简**。旧 shim (`dispatcher.py`, `circuit_breaker.py` 等) 已彻底拔除。
- `src/vibe3/manager/`：**已对齐**。`ManagerExecutor` 负责统一调度。

### 2. 核心语义修复 (已落地)
- **Assignee Unique Trigger**: `state_label_dispatch.py` 已降级为只读镜像，不再触发 `dispatch_manager`。
- **Queue Admission**: `ManagerExecutor` 实现了初步的 Queue 机制，容量满时自动排队而非直接拒绝。
- **Master Decoupling**: `master.py` 的 triage 决策已与 `state/ready` 标签解耦，回归纯粹的决策建议。
- **Status Perception**: `OrchestraSnapshot` 已扩展 `queued_issues` 字段，CLI `status` 面板已对齐展示。

## 目标四层架构

```
server/          ← HTTP 入口
  app.py           FastAPI + webhook router
  mcp.py           MCP server
  registry.py      装配 heartbeat + services + FastAPI

runtime/         ← 事件循环 + 执行引擎 (核心引擎)
  heartbeat.py     HeartbeatServer
  event_bus.py     GitHubEvent + ServiceBase
  executor.py      run_command()
  circuit_breaker.py  CircuitBreaker

orchestra/       ← 编排策略 + 治理 (决策层)
  config.py        全局配置
  master.py        triage AI agent (建议分配，不直接操作状态机)
  services/
    assignee_dispatch.py    唯一分发触发源
    governance_service.py   AI 治理扫描
    status_service.py       只读聚合 (感知 running/queued/blocked)
    state_label_dispatch.py 状态镜像 (不触发 dispatch)

manager/         ← 执行现场管理 (执行层)
  manager_executor.py  统一编排入口 (支持 Queue)
  flow_manager.py      flow 生命周期
  worktree_manager.py  worktree 生命周期
  command_builder.py   命令构造
  result_handler.py    结果处理
```

## 后续工作

1. **持久化 Queue**：目前 Queue 仅存在于内存，Server 重启会丢失。
2. **结构化结果反馈**：将 manager 的 dispatch 返回值从 `bool` 升级为 `DispatchResult`。
3. **治理指令集**：增强 `GovernanceService` 对队列的干预能力。
