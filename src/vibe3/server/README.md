# Server

HTTP 服务层，提供 GitHub webhook 接收、MCP 服务和健康检查。

## 职责

- FastAPI webhook 接收和签名验证
- vibe3 serve CLI（start/stop/status）
- MCP (Model Context Protocol) 服务
- Health check 端点
- Tailscale 网络集成

## 关键组件

| 文件 | 职责 |
|------|------|
| app.py | FastAPI app + webhook 路由 + CLI |
| mcp.py | MCP 服务集成 |
| registry.py | 服务初始化 + Tailscale 设置 |

## 依赖关系

- 依赖: runtime (HeartbeatServer), orchestra (服务注册), config
- 被依赖: (顶层入口，不被其他模块依赖)
