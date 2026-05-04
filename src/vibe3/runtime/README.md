# Runtime

事件驱动运行时基础设施，提供 service protocol、心跳轮询和子进程执行能力。

## 运行时模式

Orchestra 支持两种运行时模式：

1. **Always-on Server Mode** (`vibe3 serve start`): 持续运行的守护进程，支持 webhook 接收和心跳轮询
2. **Periodic Scan Mode** (`vibe3 scan`): 单次执行的治理/监督扫描，适合 cron 或 CI/CD 集成

详见 [Runtime Modes 文档](../../../docs/v3/orchestra/runtime-modes.md)

## 职责

- Service protocol（GitHubEvent + ServiceBase）
- HeartbeatServer 轮询循环和事件路由
- 子进程执行器（timeout/capture）
- CircuitBreaker 失败分类和熔断

## 关键组件

| 文件 | 职责 |
|------|------|
| service_protocol.py | GitHubEvent 模型 + ServiceBase 协议 |
| heartbeat.py | HeartbeatServer 轮询 + 事件分发 |
| executor.py | run_command 子进程执行 |
| circuit_breaker.py | 失败率追踪和服务熔断 |

## 与 server/orchestra 的关系

- **server**: HTTP 入口 — 接收 webhook，转为 GitHubEvent
- **runtime**: 事件调度 — HeartbeatServer 轮询事件，路由到 services
- **orchestra**: 业务编排 — 注册为 runtime service，处理 issue 事件

## 依赖关系

- 依赖: models, config
- 被依赖: server (启动 heartbeat), orchestra (注册 services)
