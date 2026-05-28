---
name: vibe-orchestra
description: Use when the user wants to check orchestra service health, view serve status, or report errors. Do not use for issue pool governance or roadmap planning.
---

# /vibe-orchestra - Orchestra Service 监控

监控 orchestra service 的运行状态和健康度。

## 核心原则

- **只管 service 健康状态**：不处理 issue pool 或 roadmap
- **基于真源**：只读 `vibe3 serve status` 输出
- **报告错误**：识别 FailedGate、error_log、系统错误

## Scope

**只看 orchestra service 状态**：
- serve 运行状态（running/stopped）
- FailedGate 检查
- error_log 分析
- heartbeat 状态
- dispatcher 状态
- 最近活动和事件

**不看**：
- Issue pool 管理（由 roadmap decider 负责）
- RFC issues（由 `vibe-task` 负责）
- Blocked issues（由 `vibe-task` 负责）
- 版本规划（由 `vibe-roadmap` 负责）

## Workflow

### Step 1: 查看 serve 状态

```bash
vibe3 serve status
```

### Step 2: 解析状态

从输出中提炼：

**运行状态**：
- Service 状态（running/stopped）
- PID 信息
- Port 绑定
- Uptime

**错误检查**：
- FailedGate 是否存在
- error_log 内容
- 系统错误

**最近活动**：
- Heartbeat 时间
- Dispatcher 状态
- 最近事件

### Step 3: 报告问题

```text
📋 Orchestra Service 状态

运行状态
- Status: running
- PID: 12345
- Port: 8765
- Uptime: 2 hours

健康检查
- FailedGate: None ✅
- Error Log: Empty ✅
- Heartbeat: Normal ✅

最近活动
- Last Heartbeat: 2026-05-28 23:20:00
- Dispatcher: Active
- Recent Events: 3 (last hour)

建议
- Service 运行正常，无错误
```

## 常见问题诊断

**FailedGate 存在**：
```bash
vibe3 serve resume --yes
```

**Service stopped**：
```bash
vibe3 serve start
```

**Heartbeat 异常**：
- 检查进程是否存活
- 检查端口是否被占用

## 与其他 Skills 的区别

- **vibe-orchestra**: 监控 service 运行状态
- **vibe-task**: 查看 RFC 和 blocked issues
- **vibe-roadmap**: 版本规划和 backlog triage
- **vibe-debug-serve**: 深度调试 service 问题

## Restrictions

- 不处理 issue pool 管理
- 不做 roadmap triage
- 不看 RFC 或 blocked issues
- 只报告 service 状态，不深入调试（转给 `vibe-debug-serve`）