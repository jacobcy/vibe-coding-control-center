# Flow 304 Debug: handoff_report 日志路径问题

## 问题描述

Flow 304 的 timeline 输出中，`handoff_report` 事件显示了不正确的 `log_path` 引用：

```
2026-04-22 14:24  handoff_report  opencode/my-provider/gpt-4o
  Run completed: run-2026-04-22T14:24:02.md
  - /Users/jacobcy/src/vibe-center/main/.worktrees/wt-claude-v3/temp/logs/ses_24c24a453ffeSRLA48WunFI0m2.async.log (not found)
```

### 问题点

1. **`ses_` 前缀路径是错误的**：这是 codeagent-wrapper 生成的 session ID，不应该出现在 handoff 事件中
2. **handoff 文档被错误地当作日志处理**：handoff 是 agent 主动记录的文档，应该在 agent 工作目录，不应该在执行目录拼接日志路径
3. **存在冗余的 `log_path` 记录逻辑**：需要区分：
   - **日志**：写在执行目录（如 `temp/logs/issues/issue-304/manager-2.async.log`），这是系统执行产生的日志
   - **handoff**：agent 主动记录的文档，应该在 agent 工作目录

## 代码分析

### 相关文件

| 文件 | 作用 |
|------|------|
| `src/vibe3/services/handoff_service.py` | `handoff_service._record_ref` 创建 handoff 事件 |
| `src/vibe3/execution/coordinator.py` | 添加 `log_path` 到事件 refs |
| `src/vibe3/ui/flow_ui_timeline.py` | timeline 显示逻辑，从 `refs["log_path"]` 读取 |
| `src/vibe3/agents/backends/async_launcher.py` | 日志路径分配逻辑 |

### 关键发现

1. **`handoff_service._record_ref` (第 135-154 行)**：
   - `event_refs` 只包含 `ref` 和 `verdict`，没有 `log_path`
   - 这是正确的设计

2. **`coordinator.py` (第 270-272 行)**：
   ```python
   checkpoint_refs = dict(request.refs)
   checkpoint_refs["tmux_session"] = tmux_session
   checkpoint_refs["log_path"] = log_path
   ```
   - 这里会将 `log_path` 添加到事件的 refs 中
   - 但这是为 `tmux_*_started` 事件设计的，不应该泄漏到 handoff 事件

3. **`timeline` 显示逻辑 (第 227-240 行)**：
   ```python
   log_path = event.refs.get("log_path") if isinstance(event.refs, dict) else None
   if log_path and isinstance(log_path, str):
       log_display = resolve_ref_path(...)
       _log_suffix = " [dim yellow](not found)[/]" if not Path(log_display).exists() else ""
       console.print(f"  [dim]- {log_display}[/]{_log_suffix}")
   ```
   - 会显示所有事件的 `log_path`（如果存在）

## 需要处理的任务

### 任务 1：删除 handoff_report 事件中的 `log_path` 引用

**目标**：确保 `handoff_report` 等 handoff 类型事件不包含 `log_path`

**可能的方案**：
- 方案 A：清理数据库中已存在的 handoff 事件的 `log_path` 字段
- 方案 B：修改 timeline 显示逻辑，handoff 类型事件不显示 `log_path`
- 方案 C：检查是否有代码错误地将 `log_path` 添加到 handoff 事件中

### 任务 2：确认 handoff 文档路径的正确性

**目标**：handoff 文档应该写入 agent 工作目录，而不是执行目录

**待确认**：
- `handoff report` 命令的 `report_ref` 参数应该如何处理？
- handoff 文档的实际写入路径在哪里？

### 任务 3：区分日志和 handoff 的显示

**目标**：timeline 中应该正确区分：
- 执行系统产生的日志（`tmux_*_started` 等）
- agent 主动记录的 handoff 文档

## 数据库查询参考

```bash
# 查询 handoff_report 事件的 refs 内容
uv run python -c "
from vibe3.clients import SQLiteClient
client = SQLiteClient()
events = client.get_events('task/issue-304', event_type_prefix='handoff_', limit=10)
for e in events:
    print(f\"event_type: {e.get('event_type')}\")
    print(f\"refs: {e.get('refs')}\")
    print('---')
"

# 或直接查询数据库
sqlite3 /Users/jacobcy/src/vibe-center/main/.git/vibe3/handoff.db \
  \"SELECT event_type, refs FROM flow_events WHERE branch='task/issue-304' AND event_type LIKE 'handoff%' LIMIT 5;\"
```

## 后续接手建议

1. 先查询数据库确认现有数据的 `log_path` 来源
2. 检查是否有代码错误地将 `log_path` 传递到 handoff 事件
3. 确认 handoff 文档的实际写入路径是否符合预期
4. 修复后测试验证
