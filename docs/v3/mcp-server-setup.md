# Orchestra MCP Server 配置指南

## 概述

Orchestra MCP Server 提供以下工具和资源：

### MCP 工具（4个）
- **orchestra_status**: 查看当前 orchestra 系统状态摘要
- **orchestra_issue_detail**: 查看特定 issue 的详细信息
- **orchestra_dispatch_history**: 查看最近的调度执行历史
- **orchestra_ask**: 向项目探索 agent 提问（**核心功能**）

### MCP 资源（3个）
- `orchestra://status`: 当前状态 JSON
- `orchestra://issues`: 管理的 issues 列表
- `orchestra://circuit-breaker`: Circuit breaker 状态

## 配置步骤

### 1. 确认 MCP 包已安装

MCP 是可选依赖，需要单独安装：

```bash
uv pip install mcp
```

### 2. 添加 MCP client 配置

在项目级 `.claude/settings.json` 或全局 `~/.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "orchestra": {
      "command": "uv",
      "args": ["run", "vibe3", "mcp", "run"]
    }
  }
}
```

### 3. 重启 Claude Code

配置生效后重启 Claude Code，MCP tools 会自动加载。

## 使用示例

### orchestra_ask 工具示例

```json
// 调用示例
{
  "tool": "orchestra_ask",
  "arguments": {
    "question": "What is the structure of src/vibe3/?"
  }
}
```

返回：项目探索 agent 的答案（spawned sub-agent）

### orchestra_status 工具示例

```json
// 调用示例
{
  "tool": "orchestra_status"
}
```

返回：格式化的系统状态摘要

## 注意事项

1. **Orchestra 服务必须运行**：MCP server 需要 Orchestra HTTP 服务在端口 8080 运行才能提供完整的实时状态
2. **启动 Orchestra 服务**：
   ```bash
   uv run vibe3 serve start
   ```
3. **检查状态**：
   ```bash
   uv run vibe3 serve status
   ```

## 测试 MCP Server

手动测试 MCP server：

```bash
# 发送初始化请求
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}' | uv run vibe3 mcp run

# 预期输出：MCP 协议的 JSON-RPC 响应
```

## 架构说明

- **传输方式**：stdio（标准 MCP client 传输）
- **服务实现**：`src/vibe3/server/mcp.py`
- **CLI 命令**：`src/vibe3/commands/mcp.py`
- **状态服务**：`src/vibe3/services/orchestra_status_service.py`

## 下一步

配置完成后，你可以在 Claude Code 中直接调用 `orchestra_ask` 工具来询问项目相关问题，系统会自动 spawn 一个 project explorer agent 来回答。