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
| __init__.py | 5 | 模块初始化 |
| service_protocol.py | ~20 | ServiceBase 协议 |
| circuit_breaker.py | 228 | 失败率追踪和服务熔断 |
| heartbeat.py | ~250 | HeartbeatServer 轮询循环 |

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

### service_protocol.py
定义服务协议：
- **ServiceBase**: 服务接口（on_tick）
- 支持服务注册和命名

## 与 server/orchestra 的关系

- **server**: HTTP 入口 — 提供 status endpoint
- **runtime**: 事件调度 — HeartbeatServer 轮询，触发 services
- **orchestra**: 业务编排 — 注册为 runtime service，处理 issue 事件

## 依赖关系

```
runtime/
├── heartbeat.py → service_protocol, observability.orchestra_log
├── circuit_breaker.py → （无内部依赖）
└── service_protocol.py → （无内部依赖）
```

**外部依赖**:
- loguru: 日志记录
- pydantic: 数据模型
- vibe3.models.orchestra_config: 配置模型
- vibe3.observability.orchestra_log: 事件日志（append_orchestra_event 等）

**被依赖**:
- server/: 启动 HeartbeatServer
- orchestra/: 注册 services
- services/: 实现 ServiceBase 协议

## 架构说明

**记录**: 已通过 handoff 记录此发现。