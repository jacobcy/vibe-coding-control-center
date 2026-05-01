---
document_type: standard
title: Vibe3 Serve 调试指南
status: approved
scope: debugging-entry-point
authority:
  - agent-debugging
  - serve-runtime
author: planner (Claude Opus 4.6)
created: 2026-05-01
last_updated: 2026-05-01
related_docs:
  - docs/standards/agent-debugging-standard.md
  - docs/standards/vibe3-orchestra-runtime-standard.md
  - docs/standards/vibe3-noop-gate-boundary-standard.md
  - docs/standards/vibe3-state-sync-standard.md
---

# Vibe3 Serve 调试指南

> **文档定位**：vibe3 serve 调试的统一入口点。提供"如何开始"的导航，不重复权威标准细节。
> **适用范围**：所有使用 `vibe3 serve` 的调试场景，包括 orchestra、manager、webhook 触发链路。
> **权威性**：本指南是导航入口，详细规范以引用的标准文档为准。

---

## 一、先读什么

**调试前必读的权威标准**（按优先级）：

1. **[agent-debugging-standard.md](./agent-debugging-standard.md)**：Agent 调试总入口
   - 日志规范、链路调试方法、观测手段
   - 上层业务 vs 底层触发的职责边界
   - async/tmux 观察优先原则

2. **[vibe3-orchestra-runtime-standard.md](./vibe3-orchestra-runtime-standard.md)**：运行时架构
   - 服务生命周期、service 注册、事件流转
   - 同步链/异步链执行路径

3. **[vibe3-noop-gate-boundary-standard.md](./vibe3-noop-gate-boundary-standard.md)**：no-op gate 语义
   - blocked 作为调试信号的正确理解
   - gate/block/fail 的区别与处理

4. **[vibe3-state-sync-standard.md](./vibe3-state-sync-standard.md)**：状态同步与真源定义
   - authoritative ref 的定义
   - 状态一致性检查方法

---

## 二、如何启动服务

### 2.1 当前 CLI 命令语法

**默认 async 模式**（推荐）：

```bash
uv run python src/vibe3/cli.py serve start
```

- 默认使用 async/tmux 后台执行
- 通过 tmux session 观察运行过程
- 日志写入 `temp/logs/orchestra/events.log` 和 `temp/logs/*.async.log`

**同步模式**（调试特定场景）：

```bash
uv run python src/vibe3/cli.py serve start --no-async
```

- 前台阻塞执行，Ctrl+C 停止
- 适合需要立即看到控制台输出的场景

### 2.2 常用启动选项

```bash
# 指定端口
uv run python src/vibe3/cli.py serve start --port 8080

# 指定仓库
uv run python src/vibe3/cli.py serve start --repo owner/repo

# Debug 模式（使用当前分支作为 scene base）
uv run python src/vibe3/cli.py serve start --debug

# 增加日志详细度
uv run python src/vibe3/cli.py serve start -v    # INFO
uv run python src/vibe3/cli.py serve start -vv   # DEBUG
```

**注意**：`--async` 标志已废弃，async 现在是默认行为。使用 `--no-async` 切换到同步模式。

---

## 三、如何观察

### 3.1 日志路径

| 日志类型 | 路径 | 用途 |
|---------|------|------|
| Orchestra 事件日志 | `temp/logs/orchestra/events.log` | 服务生命周期、service 调度、governance 事件 |
| Agent 会话日志 | `temp/logs/*.async.log` | 单次 agent 执行的完整输出 |
| 控制台日志 | stderr (loguru) | 实时观察 |

### 3.2 真源路径（Ground Truth）

**不要只看日志，必须交叉验证真源**：

| 真源 | 命令 | 用途 |
|-----|------|------|
| Flow 状态 | `vibe3 flow show` | 当前 flow 的状态机、事件时间线 |
| Task 状态 | `vibe3 task status` | issue 归属、执行阶段、最新 actor |
| GitHub Issue | `gh issue view <number>` | 外部可见状态、labels、comments |

**调试原则**：
- 日志告诉你"发生了什么"
- 真源告诉你"结果是什么"
- 两者必须一致，否则有状态同步 bug

---

## 四、同步链/异步链心智模型

### 4.1 执行路径

```
serve start (默认 async)
  └─> tmux session (wrapper)
       └─> execute_sync() (real business logic)
            └─> agent execution
                 └─> handoff / flow update
```

**关键理解**：
- tmux async child 只是包装层
- 真实业务逻辑在 `execute_sync()` 中运行
- 调试时关注 `execute_sync()` 的输入输出，不要被 tmux 层干扰

### 4.2 async 模式的观察方法

```bash
# 查看 tmux session
tmux ls

# 进入 tmux session
tmux attach -t <session-name>

# 查看会话日志（推荐）
tail -f temp/logs/*.async.log

# 查看 orchestra 事件日志
tail -f temp/logs/orchestra/events.log
```

---

## 五、no-op gate/block/fail 语义

### 5.1 正确理解 blocked

**blocked 不是失败，是调试信号**。

- **gate**：前置条件不满足，跳过执行（正常）
- **block**：执行条件检查失败，阻止执行（调试信号）
- **fail**：执行失败，需要修复（错误）

### 5.2 调试策略

| 状态 | 含义 | 调试动作 |
|-----|------|---------|
| gate | 前置条件不满足 | 检查前置条件是否应该满足 |
| block | 执行条件检查失败 | 检查条件检查逻辑是否正确 |
| fail | 执行失败 | 检查执行逻辑、输入数据、外部依赖 |

**常见误区**：
- ❌ 看到 blocked 就认为是 bug
- ✅ blocked 可能是正确的状态，需要理解为什么被 blocked

详细语义见 [vibe3-noop-gate-boundary-standard.md](./vibe3-noop-gate-boundary-standard.md)。

---

## 六、专项调试文档索引

针对特定场景的专项调试指南：

| 场景 | 文档 | 用途 |
|-----|------|------|
| Reviewer Webhook | [debug-reviewer-webhook.md](../v3/orchestra/debug-reviewer-webhook.md) | Webhook 触发链路、签名验证 |
| Manager 执行 | 见 agent-debugging-standard.md | 单 issue 执行链 |
| Supervisor 治理 | 见 agent-debugging-standard.md | 自动化治理链 |

**使用原则**：
- 先读本指南了解整体框架
- 再根据具体场景查专项文档
- 专项文档不应重复通用内容，只补充场景特定细节

---

## 七、常见调试场景清单

### 场景 1：服务启动失败

```bash
# 检查端口占用
lsof -i :8080

# 检查 PID 文件
cat .git/vibe3/orchestra.pid

# 检查配置
cat config/settings.yaml | grep -A 20 orchestra

# 查看错误日志
tail -f temp/logs/orchestra/events.log
```

### 场景 2：Webhook 未触发

```bash
# 检查服务健康状态
curl http://127.0.0.1:8080/health

# 检查 webhook 端点
curl -X POST http://127.0.0.1:8080/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -d '{"action":"test"}'

# 查看事件日志
tail -f temp/logs/orchestra/events.log | grep webhook
```

### 场景 3：Agent 执行异常

```bash
# 查看会话日志
tail -f temp/logs/*.async.log

# 检查 flow 状态
vibe3 flow show

# 检查 task 状态
vibe3 task status

# 检查 handoff
vibe3 handoff status <branch>
```

### 场景 4：状态不一致

```bash
# 对比 flow 状态与 GitHub issue
vibe3 flow show
gh issue view <number> --json labels,state

# 检查 authoritative ref
vibe3 handoff show <ref>

# 检查真源
vibe3 task status --trace
```

---

## 八、调试检查清单

每次调试前快速检查：

- [ ] 已阅读 [agent-debugging-standard.md](./agent-debugging-standard.md)
- [ ] 确认当前 CLI 语法（`serve start` 默认 async，`--no-async` 同步）
- [ ] 确认日志路径（`temp/logs/orchestra/`、`temp/logs/*.async.log`）
- [ ] 确认真源路径（`vibe3 flow show`、`vibe3 task status`、GitHub issue）
- [ ] 理解同步链/异步链执行路径
- [ ] 理解 no-op gate/block/fail 语义
- [ ] 根据场景查专项调试文档

---

## 九、快速参考

**启动服务**：
```bash
uv run python src/vibe3/cli.py serve start          # async (默认)
uv run python src/vibe3/cli.py serve start --no-async  # sync
```

**观察日志**：
```bash
tail -f temp/logs/orchestra/events.log  # orchestra 事件
tail -f temp/logs/*.async.log            # agent 会话
```

**检查状态**：
```bash
vibe3 flow show                          # flow 状态
vibe3 task status                        # task 状态
gh issue view <number>                   # GitHub issue
```

**进入 tmux**：
```bash
tmux ls                                  # 列出 sessions
tmux attach -t <session-name>            # 进入 session
```
