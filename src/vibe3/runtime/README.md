# Runtime

事件驱动运行时基础设施，提供 service protocol、心跳轮询和子进程执行能力。

## 运行时模式

Orchestra 支持两种运行时模式：

1. **Always-on Server Mode** (`vibe3 serve start`): 持续运行的守护进程，支持心跳轮询
2. **Periodic Scan Mode** (`vibe3 scan`): 单次执行的治理/监督扫描，适合 cron 或 CI/CD 集成

详见 [Runtime Modes 文档](../../../docs/v3/orchestra/runtime-modes.md)

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| heartbeat.py | 489 | HeartbeatServer 轮询循环、tick-driven 架构 |
| circuit_breaker.py | 228 | 失败率追踪和服务熔断 |
| cleanup_executor.py | 137 | 过期资源清理执行器 |
| periodic_check_executor.py | 115 | 定期检查执行器 |
| protocols.py | 78 | ServiceBase、CheckServiceProtocol 协议定义 |
| taxonomy.py | 83 | MODULE_CATEGORY_MAP、ModuleCategory 分类 |
| pool_exhaustion.py | 43 | 连接池耗尽检测 |
| orchestra_instance.py | 19 | Orchestra 实例信息读写 |
| __init__.py | 135 | 模块初始化、公共导出 |

**总计**: 9 文件，1327 行代码（截至 2026-07）

## 职责

- Service protocol (ServiceBase)
- HeartbeatServer 轮询循环
- 子进程执行器（timeout/capture）
- CircuitBreaker 失败分类和熔断

## 关键组件

### heartbeat.py
**HeartbeatServer** 是事件循环核心，采用 tick-driven 架构：

- 定时轮询（可配置间隔）
- 轮询 GitHub issue events
- 轮询 PR status
- 触发定时任务

核心事件循环：
```
while running:
    tick() → call registered services.on_tick()
    handle_timeouts() → cleanup stale tasks
```

### circuit_breaker.py
**CircuitBreaker** 实现熔断模式：
- **CLOSED**: 正常执行
- **OPEN**: 熔断状态，快速失败
- **HALF_OPEN**: 尝试恢复

状态转换：
- CLOSED → OPEN: 失败率超过阈值
- OPEN → HALF_OPEN: 冷却时间后尝试
- HALF_OPEN → CLOSED: 探测成功

### protocols.py
定义服务协议：
- **ServiceBase**: 服务接口（on_tick）
- **CheckServiceProtocol**: 检查服务接口
- 支持服务注册和命名

### cleanup_executor.py
**execute_expired_resource_cleanup** 清理过期资源：
- 扫描并清理过期的 handoff 记录
- 扫描并清理过期的 flow 状态
- 释放磁盘空间

### periodic_check_executor.py
**execute_periodic_check** 执行定期检查：
- 一致性检查
- 健康检查
- 资源清理

### orchestra_instance.py
Orchestra 实例管理：
- **OrchestraInstanceInfo**: 实例信息模型
- **read_instance_info**: 读取实例信息
- **write_instance_info**: 写入实例信息
- **validate_instance**: 验证实例有效性

### taxonomy.py
模块分类定义：
- **ModuleCategory**: 模块类别枚举
- **MODULE_CATEGORY_MAP**: 模块 → 类别映射

## 与 server/orchestra 的关系

- **server**: HTTP 入口 — 提供 status endpoint
- **runtime**: 事件调度 — HeartbeatServer 轮询，触发 services
- **orchestra**: 业务编排 — 注册为 runtime service，处理 issue 事件

## 三层协作关系

```
runtime (事件循环驱动)
  └─ HeartbeatServer.on_tick()
       ├─ domain.OrchestrationFacade.on_tick() → 发布 domain events
       │    └─ execution.ExecutionCoordinator → 调度 agent 执行
       │         └─ agents.CodeagentBackend.run(prompt)
       │              └─ prompts.PromptAssembler.assemble() → 装配 prompt 上下文
       └─ runtime.execute_periodic_check() → 一致性检查 & 资源清理
```

runtime 模块处于三层架构的最顶层：
- **核心职责**: 提供事件循环驱动（HeartbeatServer）
- **上层消费者**: server 启动 HeartbeatServer，domain 层注册服务
- **下游触发**: 通过 on_tick() 触发整个 execution → agents → prompts 执行链路
- **定期维护**: 执行一致性检查和资源清理

## 依赖关系

```
runtime/
├── heartbeat.py → protocols, observability.orchestra_log
├── circuit_breaker.py → （无内部依赖）
├── cleanup_executor.py → （无内部依赖）
├── periodic_check_executor.py → （无内部依赖）
├── orchestra_instance.py → （无内部依赖）
├── protocols.py → （无内部依赖）
├── taxonomy.py → （无内部依赖）
└── pool_exhaustion.py → （无内部依赖）
```

**外部依赖**:
- loguru: 日志记录
- pydantic: 数据模型
- vibe3.models.orchestra_config: 配置模型
- vibe3.observability.orchestra_log: 事件日志（append_orchestra_event 等）

**被依赖**:
- **server/**: 启动 HeartbeatServer
- **domain/**: 实现 ServiceBase 协议（OrchestrationFacade），使用 CheckServiceProtocol
- **services/orchestra/**: 注册 services，实现 CheckServiceProtocol

## 公开 APIs

| 符号 | 类型 | 消费位置 |
|------|------|---------|
| **Protocols** | | |
| ServiceBase | 协议 | domain/, services/orchestra/ |
| CheckServiceProtocol | 协议 | domain/, services/orchestra/ |
| **Heartbeat** | | |
| HeartbeatServer | 事件服务器 | server/, domain/ |
| FailedGateProtocol | 协议 | domain/ |
| get_current_tick_id | 工具函数 | domain/, services/ |
| **Circuit Breaker** | | |
| CircuitBreaker | 熔断器 | services/orchestra/ |
| CircuitState | 状态枚举 | services/orchestra/ |
| ErrorCategory | 错误分类 | services/orchestra/ |
| classify_failure | 分类函数 | services/orchestra/ |
| **Cleanup** | | |
| execute_expired_resource_cleanup | 清理函数 | domain/ |
| **Periodic Check** | | |
| execute_periodic_check | 检查函数 | domain/ |
| **Instance Management** | | |
| OrchestraInstanceInfo | 数据模型 | server/, domain/ |
| read_instance_info | 读取函数 | server/, domain/ |
| validate_instance | 验证函数 | server/ |
| write_instance_info | 写入函数 | server/ |
| **Taxonomy** | | |
| MODULE_CATEGORY_MAP | 分类映射 | domain/, services/ |
| ModuleCategory | 类别枚举 | domain/, services/ |

## execution 层接口

runtime 模块不直接被 execution 层导入。execution 层与 runtime 的连接是间接的：

- **domain.OrchestrationFacade** 实现 `ServiceBase` 协议（来自 runtime.protocols）
- **domain.OrchestrationFacade** 注册到 `HeartbeatServer`（来自 runtime.heartbeat）
- execution 层通过 domain 层的 OrchestrationFacade 间接使用 runtime 提供的事件驱动能力

这种间接依赖设计保持了 execution 层对 runtime 实现细节的解耦。

## 架构说明

**记录**: 已通过 handoff 记录此发现。