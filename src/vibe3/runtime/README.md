# Runtime

事件驱动运行时基础设施，提供 service protocol、心跳轮询和子进程执行能力。

## 运行时模式

Orchestra 支持两种运行时模式：

1. **Always-on Server Mode** (`vibe3 serve start`): 持续运行的守护进程，支持 webhook 接收和心跳轮询
2. **Periodic Scan Mode** (`vibe3 scan`): 单次执行的治理/监督扫描，适合 cron 或 CI/CD 集成

详见 [Runtime Modes 文档](../../../docs/v3/orchestra/runtime-modes.md)

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 5 | 模块初始化 |
| service_protocol.py | 51 | GitHubEvent 模型 + ServiceBase 协议 |
| circuit_breaker.py | 228 | 失败率追踪和服务熔断 |
| heartbeat.py | 296 | HeartbeatServer 轮询 + 事件分发 |

截至 2026-05，总计约 580 行。

## 职责

- Service protocol（GitHubEvent + ServiceBase）
- HeartbeatServer 轮询循环和事件路由
- 子进程执行器（timeout/capture）
- CircuitBreaker 失败分类和熔断

## 关键组件

### heartbeat.py
**HeartbeatServer** 是事件循环核心，采用双通道架构：
1. **tick 通道**: 定时轮询（可配置间隔）
   - 轮询 GitHub issue events
   - 轮询 PR status
   - 触发定时任务
2. **event 通道**: 事件驱动
   - 接收 webhook events
   - 路由到注册的 services
   - 支持事件优先级

核心事件循环：
```
while running:
    tick() → poll GitHub events
    event_queue.get() → dispatch to services
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

### service_protocol.py
定义服务协议：
- **GitHubEvent**: 统一事件模型（issue/PR/comment）
- **ServiceBase**: 服务接口（handle_event, start, stop）
- 支持事件过滤和优先级

## 与 server/orchestra 的关系

- **server**: HTTP 入口 — 接收 webhook，转为 GitHubEvent
- **runtime**: 事件调度 — HeartbeatServer 轮询事件，路由到 services
- **orchestra**: 业务编排 — 注册为 runtime service，处理 issue 事件

## 依赖关系

```
runtime/
├── heartbeat.py → service_protocol, orchestra/logging（设计例外，见下文）
├── circuit_breaker.py → （无内部依赖）
└── service_protocol.py → （无内部依赖）
```

**外部依赖**:
- loguru: 日志记录
- pydantic: 数据模型
- vibe3.models.orchestra_config: 配置模型
- vibe3.orchestra.logging: 日志工具（**设计例外**）

**被依赖**:
- server/: 启动 HeartbeatServer
- orchestra/: 注册 services
- services/: 实现 ServiceBase 协议

## 架构问题说明

### runtime → orchestra/logging 依赖

**发现**: `heartbeat.py` 导入 `vibe3.orchestra.logging`

**问题**: runtime 作为基础设施层，理论上不应依赖上层 orchestra 模块，这违反了分层原则。

**原因**: 该依赖用于日志工具复用，可能是历史设计决策。

**处理**: 标注为"设计例外"，暂不强制重构。后续架构治理时可评估是否需要将日志工具下沉到基础层。

**记录**: 已通过 handoff 记录此发现。
