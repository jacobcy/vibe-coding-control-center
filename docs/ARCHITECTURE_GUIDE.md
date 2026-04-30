# Vibe3 Architecture Guide for AI Agents

> **文档定位**: 为 AI Agent 提供快速导航到关键架构文档的入口
> **目标读者**: AI Agent（Claude、Codex 等）
> **更新日期**: 2026-04-21

---

## 快速索引

### 核心架构文档

| 文档 | 路径 | 关键内容 | 权威性 |
|------|------|---------|--------|
| **Human-Mirror 架构** | [docs/standards/vibe3-human-mirror-architecture.md](standards/vibe3-human-mirror-architecture.md) | 核心设计哲学：系统操作 = 人类操作 | ⭐⭐⭐ 权威 |
| **事件驱动架构** | [docs/standards/vibe3-event-driven-standard.md](standards/vibe3-event-driven-standard.md) | 事件发布/订阅机制、处理器注册、向后兼容 | ⭐⭐⭐ 权威 |
| **Worktree 所有权** | [docs/standards/vibe3-worktree-ownership-standard.md](standards/vibe3-worktree-ownership-standard.md) | 执行层级（L0-L4）、worktree 语义、隔离规则 | ⭐⭐⭐ 权威 |
| **Orchestra Runtime** | [docs/standards/vibe3-orchestra-runtime-standard.md](standards/vibe3-orchestra-runtime-standard.md) | Driver/Tick/Async Child 架构、调度主循环 | ⭐⭐⭐ 权威 |
| **State Sync** | [docs/standards/v3/command-standard.md](standards/v3/command-standard.md) | Flow 状态机、状态转换规则 | ⭐⭐⭐ 权威 |

### 实现细节文档

| 文档 | 路径 | 关键内容 |
|------|------|---------|
| **Infrastructure Guide** | [docs/v3/architecture/infrastructure-guide.md](v3/architecture/infrastructure-guide.md) | 基础设施服务使用指南 |
| **Capacity Control** | [docs/v3/architecture/capacity-control.md](v3/architecture/capacity-control.md) | 容量控制详解 |
| **Dependency Handling** | [docs/v3/architecture/dependency-handling.md](v3/architecture/dependency-handling.md) | 依赖管理机制 |

### 代码规范文档

| 文档 | 路径 | 关键内容 |
|------|------|---------|
| **Python Standards** | [.claude/rules/python-standards.md](../.claude/rules/python-standards.md) | Python 代码规范、类型注解、测试要求 |
| **Coding Standards** | [.claude/rules/coding-standards.md](../.claude/rules/coding-standards.md) | 实现细节、工具选择、边界细则 |

---

## 关键概念速查

### 1. 事件驱动架构

**核心流程**：
```
Publisher.publish(event) → EventPublisher 查找订阅者 → 调用 handlers
```

**关键要点**：
- ✅ 事件类名必须与订阅字符串完全匹配
- ✅ 启动时注册 handlers（`register_event_handlers()`）
- ✅ 事件是不可变的 dataclass（`frozen=True`）
- ✅ Handler 必须有完整类型注解

**常见错误**：
- ❌ 事件名称不匹配 → handler 不执行
- ❌ 忘记注册 handler → 事件"断线"
- ❌ Handler 没有类型注解 → mypy 报错

**详细文档**: [vibe3-event-driven-standard.md](standards/vibe3-event-driven-standard.md)

---

### 2. 执行层级与 Worktree

**五层架构**：
```
L0  Orchestra / Heartbeat          -- 调度主循环
L1  Governance Service             -- 定期扫描，只操作 GitHub labels
L2  Supervisor + Apply             -- 轻量治理执行，临时 worktree 隔离
L3  Manager / Plan / Run / Review  -- 代码开发核心，独立 worktree
L4  Human collaboration            -- 人工协作流程
```

**Worktree 语义**：
- **L1**: 无 worktree（`cwd=None`）
- **L2**: 临时 worktree（`--worktree` 标志）
- **L3**: 持久 worktree（`cwd=wt_path`）

**详细文档**: [vibe3-worktree-ownership-standard.md](standards/vibe3-worktree-ownership-standard.md)

---

### 3. Dispatch Intent 事件

**事件列表**：
- `ManagerDispatchIntent` - Manager 调度意图
- `PlannerDispatchIntent` - Planner 调度意图
- `ExecutorDispatchIntent` - Executor 调度意图
- `ReviewerDispatchIntent` - Reviewer 调度意图

**关键要点**：
- 这些是 **Intent** 事件，表示"应该 dispatch"，不是"已 dispatched"
- 向后兼容：`*Dispatched` 作为别名保留
- Handler 订阅时必须使用正确的事件名称

**Handler 注册示例**：
```python
# src/vibe3/domain/handlers/dispatch.py
def register_dispatch_handlers() -> None:
    from vibe3.domain.publisher import subscribe
    
    # 新名称
    subscribe("ManagerDispatchIntent", handle_manager_dispatch_intent)
    # 向后兼容
    subscribe("ManagerDispatched", handle_manager_dispatch_intent)
```

**详细文档**: [vibe3-event-driven-standard.md](standards/vibe3-event-driven-standard.md) §三

---

### 4. Audit 事件

**事件**：`audit_recorded`

**语义**：
- 系统解析 review output，提取 verdict，写入 audit_ref
- 不是 agent 的 handoff 行为，是系统的解析行为
- 区别于 `handoff_plan` / `handoff_report` / `handoff_indicate`（agent 主动提交）

**详细文档**: [vibe3-event-driven-standard.md](standards/vibe3-event-driven-standard.md) §1.2

---

## Agent 操作指南

### 修改事件相关代码时

1. **阅读架构文档**：
   - [vibe3-event-driven-standard.md](standards/vibe3-event-driven-standard.md)
   
2. **关键检查点**：
   - ✅ 事件定义：`src/vibe3/domain/events/*.py`
   - ✅ 事件注册：`src/vibe3/domain/events/__init__.py`
   - ✅ Handler 注册：`src/vibe3/domain/handlers/*.py`
   - ✅ 事件发射：`src/vibe3/orchestra/services/*.py`

3. **测试验证**：
   ```bash
   # 类型检查
   uv run mypy src/vibe3/domain
   
   # 运行测试
   uv run pytest tests/vibe3/domain/events/
   uv run pytest tests/vibe3/domain/handlers/
   ```

### 修改 Worktree 相关代码时

1. **阅读架构文档**：
   - [vibe3-worktree-ownership-standard.md](standards/vibe3-worktree-ownership-standard.md)

2. **关键检查点**：
   - ✅ 确认执行层级（L0-L4）
   - ✅ 确认 worktree 语义（临时 vs 持久）
   - ✅ 确认隔离边界（是否需要 `--worktree` 标志）

### 修改 Orchestra 相关代码时

1. **阅读架构文档**：
   - [vibe3-orchestra-runtime-standard.md](standards/vibe3-orchestra-runtime-standard.md)
   - [vibe3-event-driven-standard.md](standards/vibe3-event-driven-standard.md)

2. **关键检查点**：
   - ✅ 理解 Driver/Tick/Async Child 架构
   - ✅ 理解事件发布时机
   - ✅ 理解容量控制机制

---

## 常见问题

### Q1: 事件发出但没有执行

**可能原因**：
1. Handler 未注册 → 检查 `register_*_handlers()` 是否在启动时调用
2. 事件名称不匹配 → 检查 `subscribe("EventName", handler)` 中的字符串
3. Handler 抛出异常 → 查看日志中的 ERROR 信息

### Q2: 如何添加新事件

**步骤**：
1. 在 `src/vibe3/domain/events/*.py` 定义事件类
2. 在 `src/vibe3/domain/events/__init__.py` 添加到 `EVENT_TYPES` 和 `__all__`
3. 在 `src/vibe3/domain/handlers/*.py` 实现 handler
4. 在 `src/vibe3/domain/handlers/__init__.py` 注册 handler
5. 在发射点 `publish(event)`

### Q3: 如何重命名事件

**步骤**：
1. 重命名事件类
2. 添加向后兼容别名
3. 更新 EVENT_TYPES 注册表（新旧名称都映射）
4. Handler 订阅新旧两个名称
5. 更新文档
6. 提交变更

**详细指南**: [vibe3-event-driven-standard.md](standards/vibe3-event-driven-standard.md) §5.5

---

## 文档维护

### 更新此文档

当添加新的架构文档或重要变更时，更新此文档：
1. 在"快速索引"中添加新文档条目
2. 在"关键概念速查"中添加新概念
3. 更新"常见问题"部分

### 文档权威性

- **权威文档**: 标记 ⭐⭐⭐ 的文档是唯一权威来源
- **参考文档**: 其他文档用于补充说明，如有冲突以权威文档为准
- **代码为准**: 最终实现以代码为准，文档记录意图

---

**维护者**: Vibe Team
**最后更新**: 2026-04-21
