# Runtime

事件驱动运行时基础设施，提供事件总线、心跳轮询和子进程执行能力。

## 职责

- EventBus 事件模型和服务接口（ServiceBase）
- HeartbeatServer 轮询循环和事件路由
- 子进程执行器（timeout/capture）
- CircuitBreaker 失败分类和熔断

## 关键组件

| 文件 | 职责 |
|------|------|
| event_bus.py | GitHubEvent 模型 + ServiceBase 接口 |
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
