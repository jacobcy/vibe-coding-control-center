# Supervisor Handoff Standard

> 轻量治理链路（L2）的完整规范：触发、派发、执行、生命周期、与 Manager (L3) 的边界。

## 定位

Supervisor 是 Vibe Center 的**轻量治理链路**，负责处理带有 `supervisor + state/handoff` labels 的 GitHub issues。

**核心设计原则**：
- 一次性治理：不追踪开发过程，只关注 issue 最终状态
- 无 Flow：不创建 `flow_state`、不注册 `flow_issue_links`
- 临时隔离：执行使用临时 worktree，session orphaned 后清理
- 快速处理：label 变更、comment、issue close、文档/测试修复

**Supervisor 可以创建 PR**（见 `supervisor/apply.md`）：文档/测试修复 → commit → push → PR。PR 合并由人工处理。

与 Manager (L3) 的对比：

| 特性 | Supervisor (L2) | Manager (L3) |
|------|-----------------|-------------|
| 定位 | 轻量治理 | 重量开发 |
| Flow 注册 | 无 | `flow_state` + `flow_issue_links` |
| Branch | L2 临时 branch（无永久记录） | `task/issue-N`（永久） |
| Worktree | 临时（session orphaned 后清理） | 永久（直到 flow done） |
| State 管理 | GitHub labels | GitHub labels + `flow_status` |
| 质量门禁 | 跳过 noop gate | Noop gate 检查 state 变化 |
| 失败处理 | 系统移除 `state/handoff` label | `fail_issue()` → `state/blocked` |
| 扫描频率 | 每 `interval_ticks` tick（默认 4） | 每 tick（frozen queue） |
| 产物 | GitHub comment / issue close / PR | `plan_ref` / `audit_ref` / PR |

## 触发条件

Supervisor issue 必须同时具有两个 GitHub labels：

1. **supervisor** — 由 governance scan 或人工添加，标识治理 issue
2. **state/handoff** — 由 governance 或人工添加，标识已 handoff 到 supervisor

扫描逻辑（`iter_supervisor_identified_events`）过滤 **open issues** 中 `supervisor + state/handoff` 的。

**关键**：扫描只看 `state="open"` 的 issues。Agent 关闭 issue 后，下次扫描不再匹配。

## 生命周期

### 正常流程（Agent 主动）

```
Governance scan → 创建 supervisor issue (supervisor + state/handoff)
  ↓
Supervisor scan (每 interval_ticks tick)
  ↓
发现 supervisor + state/handoff (open issue)
  ↓
Apply agent 在临时 worktree 执行:
  1. 核查 issue findings
  2. 文档/测试修复 → commit → push → PR create（授权范围内）
  3. Comment 结果（以 [apply] 开头）
  4. Close issue
  ↓
Issue 已关闭 → state="open" 过滤不再匹配 → 不会重新扫描
```

### 异常流程（系统被动兜底）

```
Agent 执行失败 / 未关闭 issue:
  ↓
execute_sync() except 块:
  - ErrorTrackingService 记录错误
  - lifecycle "aborted" 事件
  - 系统移除 state/handoff label
  ↓
下次扫描 → issue 只有 supervisor label（无 handoff）→ 不匹配
```

### Agent 主动 vs 系统被动

| 动作 | 由谁执行 | 说明 |
|------|----------|------|
| 关闭 issue | **Agent 主动** | `supervisor/apply.md`：完成后关闭当前治理 issue |
| Commit / Push / PR | **Agent 主动** | `supervisor/apply.md`：L2 临时分支完成修改、commit、push、pr create |
| Comment 结果 | **Agent 主动** | 以 `[apply]` 开头的正式结果评论 |
| 移除 `state/handoff` label | **系统被动兜底** | 防止 agent 未关闭 issue 时无限重派发 |

**正常情况下 agent 关闭了 issue，系统侧的 label 清理不会执行到（issue 已经 closed，不会被扫描到）。**

## 临时 Worktree 清理时机

Supervisor 使用临时 worktree（`.worktrees/tmp/{issue_number}`），清理时机：

| 场景 | 清理触发 | 说明 |
|------|----------|------|
| 正常完成 | 下次同一 issue 派发时（如果还存在）或 session orphaned 检测 | 不是执行完立即清理 |
| 异常终止 | `reconcile_live_state()` 检测到 orphaned session 时 | tmux session 不存在但记录存在 |

**关键发现**：临时 worktree 不是执行完立即清理，而是：
1. 下次同一 issue 派发时，如果旧的临时 worktree 还存在，先清理再创建新的
2. `reconcile_live_state()` 检测到 orphaned session 时清理

**PR 的影响**：
- Supervisor 创建 PR 后关闭 issue → PR branch 仍然存在（git 分支）
- Tmux session 结束 → session orphaned → 清理临时 worktree
- **但 PR 的 git branch 和提交仍然存在**，PR 可以继续 review 和合并

## 执行一次性保证

Supervisor 只执行一次，两种路径：

1. **正常路径**：Agent 关闭 issue → `state="open"` 过滤排除 → 不再扫描
2. **异常路径**：系统移除 handoff label → 双 label 条件不满足 → 不再派发

## 完整执行路径（代码级）

```
on_tick()
  on_supervisor_scan()                     [每 interval_ticks tick]
    iter_supervisor_identified_events()    # 过滤 supervisor + state/handoff + open
      SupervisorIssueIdentified event
        handle_supervisor_issue_identified()
          CLI self-invocation: tmux wrapper
            internal apply N --no-async
              run_issue_role_sync(SUPERVISOR_CLI_SYNC_SPEC)
                CodeagentExecutionService.execute_sync()
                  _prepare_sync_context()    # lifecycle started
                  CodeagentBackend.run()     # codeagent-wrapper
                  _finalize_sync_execution():
                    - lifecycle completed
                    - SKIP noop gate
                    - cleanup supervisor handoff label (系统兜底)
```

## 为什么跳过 Noop Gate

Noop gate 检查 GitHub issue 的 `state/` label 是否发生变化。对 Supervisor：
- Agent 被期望**关闭** issue，而非修改 state label
- issue 关闭后，`state/handoff` label 仍存在 → gate 检测"未变化"→ block
- **任何情况都会误判为 noop**，因此 supervisor 完全跳过 gate

## 为什么不调用 fail_issue()

`fail_issue()` 内部查找 `get_flows_by_issue(N, role="task")`，Supervisor 无 task flow：
- 查询返回空列表
- `_ensure_flow_state_for_issue()` 直接 return
- `blocked_reason` 静默丢失

Supervisor 失败时系统直接移除 handoff label，让 issue 脱离自动派发循环。

## 容量控制

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `supervisor_max_concurrent` | 2 | 最大并发 supervisor 执行数 |
| `interval_ticks` | 4 | 扫描间隔（与 governance 同频） |
| `worktree_requirement` | TEMPORARY | 临时 worktree |

### 扫描调度

`on_supervisor_scan()` 在 `on_tick()` 中位于 FailedGate check 之后、L3 dispatch 之前：

```python
async def on_tick(self):
    self.on_heartbeat_tick()         # Governance [interval_ticks gating]
    # FailedGate check (阻断所有派发包括 supervisor)
    await self.on_supervisor_scan()   # Supervisor [interval_ticks gating]
    await self._coordinator.coordinate()  # L3 dispatch
```

## 可观测性

| 查询方式 | 是否可用 | 说明 |
|----------|----------|------|
| `vibe3 task status` | 部分 | Supervisor section 独立显示 |
| `vibe3 task show <issue>` | 部分 | 仅 runtime_sessions 数据 |
| `vibe3 flow show` | 不可用 | 无 flow 记录 |
| GitHub issue view | 可用 | comment / close / PR 状态 |
| tmux session | 可用 | `vibe3-supervisor-issue-N` |

## 相关文件

### 核心实现

| 文件 | 职责 |
|------|------|
| `src/vibe3/domain/handlers/supervisor_scan.py` | 事件处理器，CLI self-invocation 派发 |
| `src/vibe3/domain/events/supervisor_apply.py` | Supervisor 事件定义 |
| `src/vibe3/roles/supervisor.py` | 角色定义、request builder、事件过滤 |
| `src/vibe3/execution/codeagent_runner.py` | 同步执行壳，supervisor 专属跳过/清理逻辑 |
| `src/vibe3/environment/worktree.py` | `acquire_temporary_worktree`、`release_temporary_worktree` |
| `src/vibe3/environment/session_registry.py` | session orphaned 检测，触发 worktree 清理 |

### 配置

| 文件 | 职责 |
|------|------|
| `src/vibe3/models/orchestra_config.py` | `SupervisorHandoffConfig`（`interval_ticks` 等） |
| `src/vibe3/domain/orchestration_facade.py` | `on_supervisor_scan()` + interval gating |

### 角色材料

| 文件 | 职责 |
|------|------|
| `supervisor/apply.md` | Supervisor apply 权限契约、执行模式、输出要求 |

### 标准

| 文件 | 职责 |
|------|------|
| `docs/standards/vibe3-event-driven-standard.md` | L2 事件层级定义 |
| `docs/standards/vibe3-worktree-ownership-standard.md` | L2 临时 worktree 语义 |
| `docs/standards/vibe3-noop-gate-boundary-standard.md` | Gate 边界定义 |
| `docs/standards/github-labels-reference.md` | Label 语义参考 |
