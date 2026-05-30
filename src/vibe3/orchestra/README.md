# Orchestra 模块

`vibe3 serve` 的核心是一个长期运行的 driver / 调度器。

统一 runtime 语义以
[docs/standards/v3/orchestra-runtime-standard.md](docs/standards/v3/orchestra-runtime-standard.md)
为准。

## 架构

```
vibe3 serve start --port 8080
  |
  +-- FastAPI (0.0.0.0:8080)
  |     GET  /status
  |     MCP  /mcp (optional)
  |
  +-- HeartbeatServer (asyncio)
        Semaphore(3)            最多 3 个并发任务
        |
        +-- 心跳路径 (每 900s)
              遍历已注册 service -> on_tick()
```

## 触发机制

当前应按两层理解：

### 1. Governance / Supervisor 决定 ready

以下角色负责把 issue 推进到 `state/ready`：

- governance
- supervisor / triage agent
- 人工治理

### 2. State Trigger 消费已有状态

driver 在 heartbeat tick 中消费已有 `state/*`：

- `state/ready` -> manager
- `state/claimed` -> plan
- `state/in-progress` -> run
- `state/review` -> review

补充：

- `state/blocked` 表示无法继续推进（包括业务阻塞和执行失败）
  - blocked_reason 字段记录具体原因
  - 人工 resume 恢复执行

## 内置 Service

| Service | 触发方式 | 功能 |
|---------|----------|------|
| `OrchestrationFacade` | heartbeat tick | 统一入口：governance scan + supervisor scan + dispatch |

## 注册自定义 Service

```python
from vibe3.runtime import ServiceBase, HeartbeatServer

class MyService(ServiceBase):
    async def on_tick(self) -> None:
        ...  # 每 900s 轮询执行

heartbeat = HeartbeatServer(config)
heartbeat.register(MyService())
```

## 部署（开发服务器）

```bash
# 启动
vibe3 serve start --port 8080

# 后台运行
tmux new -d -s orchestra 'vibe3 serve start --port 8080'
```

## 配置

`config/v3/settings.yaml` 中的 `orchestra` 节：

```yaml
orchestra:
  enabled: true
  polling_interval: 900        # 正常模式默认 15 分钟
  debug_polling_interval: 60   # debug 模式默认 1 分钟
  port: 8080
  repo: owner/repo             # 留空则用当前 repo
  max_concurrent_flows: 3
  manager_usernames:
    - vibe-manager
```
