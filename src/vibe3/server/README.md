# Server

HTTP 服务层，提供 GitHub webhook 接收、MCP 服务和健康检查。

## 文件列表

| 文件 | 行数 | 职责 |
|------|------|------|
| __init__.py | 1 | 模块初始化 |
| server_utils.py | 32 | 服务辅助函数 |
| webhook_utils.py | 96 | Webhook 签名验证和事件解析 |
| mcp.py | 254 | MCP (Model Context Protocol) 服务集成 |
| registry.py | 417 | 服务初始化、依赖注入、Tailscale 设置 |
| app.py | 482 | FastAPI app + webhook 路由 + CLI 入口 |

截至 2026-05，总计约 1282 行。

## 职责

- FastAPI webhook 接收和签名验证
- vibe3 serve CLI（start/stop/status）
- MCP (Model Context Protocol) 服务
- Health check 端点
- Tailscale 网络集成

## 关键组件

### app.py
FastAPI 应用和 CLI 入口，提供命令：
- `vibe3 serve start`: 启动服务器
- `vibe3 serve stop`: 停止服务器
- `vibe3 serve status`: 查看服务器状态
- `vibe3 serve resume`: 恢复服务器

路由定义：
- `/webhook`: GitHub webhook 端点
- `/health`: 健康检查端点
- `/mcp`: MCP 服务端点

### registry.py
服务注册和装配中心：
1. **依赖注入**: 初始化 GitHubClient, SQLiteClient, GitClient
2. **服务组装**: 创建 OrchestrationFacade, HeartbeatServer
3. **Tailscale 集成**: 配置 Tailscale 网络
4. **状态管理**: 维护服务状态（running/stopped）

架构角色：
- registry.py 是 server 的装配点
- 负责创建和连接所有组件
- 提供 get_app_state() 供 app.py 使用

### webhook_utils.py
Webhook 处理工具：
- `verify_signature()`: GitHub webhook 签名验证
- `parse_event()`: 解析 GitHub event
- 支持 push, pull_request, issues 等事件类型

### mcp.py
MCP 服务集成：
- 实现 Model Context Protocol
- 提供 AI 模型上下文服务
- 支持工具调用和资源访问

### server_utils.py
辅助函数：
- 日志配置
- 错误处理
- 工具函数

## 依赖关系

```
server/
├── app.py → registry, clients/git_client, agents/backends, config/orchestra_settings, observability/logger, orchestra/logging
├── registry.py → clients (github, sqlite, git), domain/orchestration_facade, runtime (heartbeat, circuit_breaker), environment/session_registry, execution (capacity_service, flow_dispatch, issue_role_support), roles/registry, services/orchestra_status_service, orchestra (logging, services)
├── webhook_utils.py → runtime/heartbeat, runtime/service_protocol
├── mcp.py → （无内部依赖）
└── server_utils.py → （无内部依赖）
```

**外部依赖**:
- fastapi: Web 框架
- typer: CLI 框架
- uvicorn: ASGI 服务器
- loguru: 日志记录
- vibe3.agents: 后端配置
- vibe3.clients: GitHubClient, SQLiteClient, GitClient
- vibe3.config: orchestra_settings (load_orchestra_config)
- vibe3.domain: OrchestrationFacade
- vibe3.environment: SessionRegistryService
- vibe3.exceptions: ErrorTrackingService (conditional import)
- vibe3.execution: CapacityService, FlowManager, issue_role_support
- vibe3.models: 配置模型
- vibe3.observability: 日志配置
- vibe3.orchestra: logging, failed_gate, services (comment_reply, state_label_dispatch)
- vibe3.roles: LABEL_DISPATCH_ROLES
- vibe3.runtime: HeartbeatServer, GitHubEvent
- vibe3.services: OrchestraStatusService

**被依赖**:
- (顶层入口，不被其他模块依赖)

## 架构说明

### server 作为装配点

server 模块是应用的顶层入口，承担装配职责：

1. **依赖注入流程**:
   ```
   registry.py
     → 初始化 clients (github, sqlite, git)
     → 创建 domain services (OrchestrationFacade)
     → 启动 runtime (HeartbeatServer)
     → 注册 services
   ```

2. **启动流程**:
   ```
   app.py (CLI)
     → registry.py (装配)
     → HeartbeatServer.start()
     → uvicorn.run()
   ```

3. **请求流程**:
   ```
   GitHub webhook
     → app.py (FastAPI route)
     → webhook_utils (验证、解析)
     → HeartbeatServer.dispatch(event)
     → OrchestrationFacade.handle(event)
   ```

### 与 runtime/orchestra 的关系

- **server**: HTTP 入口 + 装配点
- **runtime**: 事件调度
- **orchestra**: 业务编排
- **domain**: 业务逻辑

server → runtime → orchestra → domain（单向依赖）
