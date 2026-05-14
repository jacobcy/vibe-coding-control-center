# 统一 Blocked 状态设置方案

**日期**：2026-05-14
**状态**：设计完成，待实施
**分支**：`fix/blocked-reason-not-displayed`

---

## 问题背景

当前系统存在多个设置 blocked 状态的方式，导致数据不一致：

### 问题表现

1. **`vibe task status` 不显示 blocked 原因**
   - Manager 在循环保护时设置了 `state/blocked` label
   - 但 `blocked_reason` 字段为空
   - 用户看不到 blocked 的具体原因

### 根本原因

Manager 在设置 blocked 时，使用了两个不同的执行路径：

1. **正确路径**（首次 blocked）：
   ```bash
   vibe3 handoff indicate docs/handoff/block.md --blocked-by "原因"
   ```
   - ✅ 写入 `blocked_reason` 到 flow_state
   - ✅ 修改 GitHub label
   - ✅ 写入 handoff 事件

2. **问题路径**（resume 后再次 blocked）：
   - Manager 只修改 GitHub label
   - ❌ 没有写入 `blocked_reason`
   - 导致 `vibe task status` 无法显示原因

### 现有命令的职责混乱

| 命令 | 写 blocked_reason | 改 issue label | 加 comment |
|------|-------------------|----------------|------------|
| `vibe3 flow blocked --reason` | ✅ | ❌ | ❌ |
| `vibe3 handoff indicate --blocked-by` | ✅ | ❌ | ❌ |
| `block_manager_noop_issue()` | ✅ | ✅ | ✅ |

**问题**：
- 只有系统内部函数做了完整操作
- 用户可见的 CLI 命令都不完整
- Manager 不知道应该用哪个

---

## 设计目标

1. **统一入口**：`vibe3 flow blocked --reason` 成为设置 blocked 的唯一规范入口
2. **完整行为**：一个命令完成三件事（写 flow + 改 label + 加 comment）
3. **最小改动**：增强现有方法，删除重复逻辑，复用底层代码
4. **保持兼容**：不破坏现有 API 和使用习惯

---

## 解决方案

### 架构设计

```
┌───────────────────────────────────────────────────────────────┐
│ 改动后的职责分层                                              │
├───────────────────────────────────────────────────────────────┤
│ vibe3 flow blocked --reason "xxx"                            │
│   → FlowLifecycleMixin.block_flow()                          │
│     ✅ 写 blocked_reason 到 flow_state                        │
│     ✅ 写 flow_blocked 事件                                    │
│     ✅ 改 issue label 为 state/blocked ← 新增                 │
│     ✅ 加 issue comment ← 新增                                 │
├───────────────────────────────────────────────────────────────┤
│ vibe3 handoff indicate <file> --blocked-by "xxx"             │
│   → HandoffService._record_ref()                             │
│     ✅ 写 blocked_reason 到 flow_state                        │
│     ✅ 写 handoff_indicate 事件                                │
│     ❌ 不改 issue label (保持现状)                             │
│     ❌ 不加 issue comment (保持现状)                           │
├───────────────────────────────────────────────────────────────┤
│ block_manager_noop_issue(issue_number, reason)               │
│   → 内部调用 FlowLifecycleMixin.block_flow() ← 重构           │
│     (删除 _ensure_flow_state_for_issue 重复逻辑)              │
└───────────────────────────────────────────────────────────────┘
```

**关键原则**：
- `flow blocked` = 完整的 blocked 设置（flow + issue）
- `handoff indicate --blocked-by` = 只记录元数据，不改 issue 状态
- 底层代码复用，删除重复逻辑

---

## 实施方案

### 改动 1：增强 `FlowLifecycleMixin.block_flow()`

**文件**：`src/vibe3/services/flow_block_mixin.py`

**改动内容**：
- 在写完 `blocked_reason` 后，增加 issue state 转换逻辑
- 如果 flow 有关联的 `task_issue_number`，则：
  1. 通过 `LabelService.confirm_issue_state()` 修改 label 为 `state/blocked`
  2. 通过 `GitHubClient.add_comment()` 添加统一的 comment

**代码示例**：
```python
def block_flow(self, branch, reason=None, blocked_by_issue=None, actor=None):
    # ... existing logic to write blocked_reason ...

    # NEW: Transition issue state
    flow_data = self.store.get_flow_state(branch)
    issue_number = flow_data.get("task_issue_number") if flow_data else None

    if issue_number:
        # Add comment
        comment = f"[manager] 已切换为 state/blocked。\n\n原因：{reason}" if reason else None

        # Transition issue state
        from vibe3.services.label_service import LabelService
        LabelService().confirm_issue_state(
            issue_number,
            to_state=IssueState.BLOCKED,
            actor=effective_actor,
            force=False,
        )

        # Add comment if provided
        if comment:
            from vibe3.clients.github_client import GitHubClient
            GitHubClient().add_comment(issue_number, comment)
```

**改动量**：约 15-20 行新增代码

---

### 改动 2：重构 `block_manager_noop_issue()`

**文件**：`src/vibe3/services/issue_failure_service.py`

**改动内容**：
- 删除 `_ensure_flow_state_for_issue()` 函数（约 40 行重复代码）
- 改为调用 `FlowService.block_flow()` 复用逻辑
- 保留 `blocked` 事件记录（用于 observability）

**代码示例**：
```python
def block_manager_noop_issue(*, issue_number, repo, reason, actor):
    # Find flow for issue
    flows = store.get_flows_by_issue(issue_number, role="task")
    if not flows:
        return

    branch = str(flows[0].get("branch") or "").strip()
    if not branch:
        return

    # Reuse block_flow()
    from vibe3.services.flow_service import FlowService
    FlowService().block_flow(branch, reason=reason, actor=actor)

    # Add block event for observability
    store.add_event(branch, "blocked", actor, detail=reason, refs={"issue": str(issue_number)})
```

**改动量**：约 10-15 行修改，删除 40 行重复代码

---

### 改动 3：CLI 层保持不变

**文件**：`src/vibe3/commands/flow_lifecycle.py`

**改动内容**：无需修改
- CLI 参数不变：`vibe3 flow blocked --reason "xxx"`
- 底层自动完成：写 flow + 改 label + 加 comment

---

## 数据流

```
vibe3 flow blocked --reason "循环保护触发"
       │
       ▼
FlowLifecycleMixin.block_flow(branch="task/issue-372", reason="循环保护触发")
       │
       ├─► 写 flow_state: blocked_reason="循环保护触发"
       ├─► 写 flow_events: type="flow_blocked"
       ├─► 改 GitHub label: state/handoff → state/blocked
       └─► 加 GitHub comment: "[manager] 已切换为 state/blocked。原因：循环保护触发"
```

---

## 用户使用体验

### Manager 设置 blocked

**推荐方式**：
```bash
vibe3 flow blocked --reason "循环保护触发"
```

**效果**：
- ✅ `vibe task status` 显示 blocked 原因
- ✅ GitHub issue 有 `state/blocked` label
- ✅ Issue comment 说明原因

---

### Manager 记录 handoff + blocked

**使用场景**：有 handoff 文档要记录时

```bash
vibe3 handoff indicate docs/handoff/block.md \
  --next-step "Fix webhook" \
  --blocked-by "Webhook unreachable"
```

**效果**：
- ✅ 写入 `blocked_reason`
- ✅ 写入 `indicate_ref` 和 handoff 事件
- ❌ 不修改 issue label（保持当前状态）

**注意**：如果需要完整 blocked 设置，应该再用 `vibe3 flow blocked`

---

### 系统 no-op gate 触发

**内部调用**（自动复用 `block_flow()`）：
```python
block_manager_noop_issue(issue_number=372, reason="state unchanged")
```

**效果**：与 `vibe3 flow blocked` 相同

---

## 改动影响评估

| 改动点 | 影响范围 | 风险 | 测试覆盖 |
|--------|----------|------|----------|
| 增强 `block_flow()` | CLI + 系统调用 | 低 | 需补充单元测试 |
| 重构 `block_manager_noop_issue()` | 系统内部函数 | 低 | 现有测试覆盖 |
| 删除 `_ensure_flow_state_for_issue()` | 减少重复代码 | 无 | 删除代码 |
| CLI 层 | 无改动 | 无 | 无需改动 |

---

## 改动量统计

| 类型 | 行数 |
|------|------|
| 新增代码 | 约 20-30 行 |
| 删除代码 | 约 40 行 |
| **净减少** | **约 10-20 行** |

---

## 实施步骤

1. ✅ 创建分支 `fix/blocked-reason-not-displayed`
2. 增强 `FlowLifecycleMixin.block_flow()`
3. 重构 `block_manager_noop_issue()`
4. 删除 `_ensure_flow_state_for_issue()` 重复代码
5. 补充单元测试
6. 本地验证
7. 提交 PR

---

## 验证标准

### 功能验证

1. **基本功能**：
   ```bash
   vibe3 flow blocked --reason "测试原因"
   # 预期：flow_state 有 blocked_reason，issue 有 state/blocked label
   ```

2. **显示验证**：
   ```bash
   vibe task status
   # 预期：Blocked Issues 显示原因
   ```

3. **事件验证**：
   ```bash
   vibe3 flow show <branch>
   # 预期：Timeline 显示 flow_blocked 事件
   ```

### 回归测试

1. `vibe3 handoff indicate --blocked-by` 保持原有行为
2. `block_manager_noop_issue()` 内部调用正常工作
3. 现有测试全部通过

---

## 附录：相关文档

- [SOUL.md](../../SOUL.md) - 项目宪法
- [CLAUDE.md](../../CLAUDE.md) - 项目上下文
- [supervisor/manager.md](../../supervisor/manager.md) - Manager 执行规范
