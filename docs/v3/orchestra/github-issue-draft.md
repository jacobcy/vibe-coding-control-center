# [RFC] Orchestra 调度器：任务板驱动的自主 Implementation Run

## 完整工作循环（TL;DR）

整合后人类只在两个点介入：

```
① 写 GitHub Issue + 加标签 orchestra:ready
② 收到 PR 通知 → Review → Merge
```

中间全自动：Orchestra daemon 发现 issue → 启动 Claude Agent（无交互）→ Agent 自主实现 → 提 PR。
Agent 不需要逐步确认，用沙箱（workspace 隔离）替代确认，只能写当前 issue 的 workspace。

---

## 背景

[openai/symphony](https://github.com/openai/symphony) 最近发布，核心理念是把工程师从"监督单个 agent 执行"提升到"管理工作本身"。

我们分析了 Symphony 的 [SPEC.md](https://github.com/openai/symphony/blob/main/SPEC.md) 之后，结论是：**Vibe Center v3 的多 agent 编排体系比 Symphony 更完整**。

Symphony 的 agent 模型是"单 agent per issue"：
```
issue → 一个 agent 从头做到尾 → PR
```

Vibe Center v3 的 agent 模型是"多 agent per flow，有流程控制"：
```
issue
  → planner agent ──handoff──→ executor agent ──handoff──→ reviewer agent
       写 plan/spec                  实现代码                    audit
                                                                    ↓
                                                             主控汇总 → PR
```

`handoff.db` 里的 `planner_actor`、`executor_actor`、`reviewer_actor` 字段，正是为这个多 agent 责任链设计的。两个系统的终点相同（issue 进，PR 出），但中间过程的工程复杂度不同。

**Symphony 真正值得借鉴的是调度工程逻辑**，不是 agent 模型：

| Symphony 工程逻辑 | 价值 | Vibe Center 现状 |
|-----------------|------|----------------|
| Orchestrator 状态机（claimed/running/retry set） | ⭐⭐⭐ | 无，并发时会重复 dispatch |
| Reconciliation loop（issue 变 terminal → 停 agent） | ⭐⭐⭐ | 无，孤儿进程风险 |
| WORKFLOW.md 规范（标准化 prompt 模板格式） | ⭐⭐ | 无等价物 |
| Workspace hook 体系（after_create/before_run/after_run） | ⭐⭐ | vibe3 flow new 部分覆盖 |

**Orchestra 设计策略：借鉴 Symphony 的 Orchestrator 状态机和 Reconciliation loop，叠加在 v3 已有的 handoff 责任链之上，使用 Python 实现。**

## 设计策略

**不直接引入 Symphony Elixir 运行时**，而是将其核心逻辑移植进 Vibe Center v3：

### Phase 1：WORKFLOW.md + GitHub Issues 适配器

在项目根新增 `WORKFLOW.md`（兼容 Symphony SPEC §5 格式），让 repo 立即对 Symphony 生态兼容：

```yaml
---
tracker:
  kind: github
  active_states: ["todo", "in_progress"]
  terminal_states: ["done", "archived"]

workspace:
  root: .worktrees   # 复用现有 worktree 目录

hooks:
  after_create: |
    git fetch origin main --quiet
  before_run: |
    source ~/.vibe/loader 2>/dev/null || true
---

# Vibe Center Workflow Prompt
...
```

实现 `src/vibe3/orchestra/tracker.py`，用 `gh` CLI 实现 GitHub Issues 适配：
- `fetch_candidates()` — 拉取带 `orchestra:ready` 标签的 issues
- `fetch_states_by_ids()` — 批量状态刷新（reconcile 用）

### Phase 2：Orchestra 调度器

实现 `src/vibe3/orchestra/scheduler.py`，核心调度逻辑：

**Agent 选择：Claude Code headless，简化实现。**

Symphony SPEC §10 的 Agent Runner 是专为 `codex app-server` JSON-RPC 协议设计的，实现复杂。Claude Code 有 headless 模式可以完全绕过这层：

```python
# scheduler 里 dispatch 一个 issue，直接启动 agent
result = subprocess.run(
    ["claude", "-p", rendered_prompt,
     "--output-format", "json",
     "--cwd", workspace],
    capture_output=True
)
```

agent 启动从"实现完整 JSON-RPC 协议"变成"执行一条命令"，`scheduler.py` 保持简洁。

轮询 tick 逻辑（借鉴 Symphony SPEC §8）：
1. reconcile：检查运行中任务的 tracker 状态
2. fetch：拉取 active issues
3. dispatch：对符合条件的 issue 执行 `vibe3 flow new` + `flow bind task` + 启动 claude headless

状态机映射到 v3 `handoff.db` 的 `flow_state.flow_status`：
- `Unclaimed` → issue 存在但无对应 flow
- `Claimed/Running` → `flow_status: active` + `session_id` 非空
- `RetryQueued` → `flow_status: active` + `session_id` 为空（等待重试）
- `Released` → `flow_status: done` / PR merged

### Phase 2.5：`vibe3 flow status` 扩展（监控面板）

不新增命令。Orchestra scheduler dispatch 一个 issue 时，往 `handoff.db` 的 `flow_state` 表写入：
- `latest_actor` = `"claude/sonnet-4.5"`
- `session_id` = 会话标识

`vibe3 flow status` 读取时自动展示：

```
Flow: fix-login
  Branch:     task/fix-login
  Status:     active
  Task Issue: #42
  Agent:      claude/sonnet-4.5 · running 12m   ← 有 agent 时显示
  PR:         #201 (draft)
  Next:       implement redirect logic
```

agent 完成后 scheduler 清空 `session_id`，该行自动消失。v3 的 `flow_state` 表已预留这两个字段，零 schema 变更。

### Phase 3：Workflow Skill

新增 Skill，处理 proof-of-work bundle 生成：
- CI 状态（`vibe3 flow review` 输出）
- diff 复杂度分析
- 自动调用 `vibe3 flow pr` 提交 PR

## 关键约束

- 保持 Python 技术栈，不引入 Elixir 运行时
- 并发安全：用数据库锁保护 `handoff.db` 写入
- 遵守 Agent 与 worktree 一对一原则：不自行新建物理 worktree，必须通过 `vibe3 flow new`
- polling interval ≥ 30s（GitHub API 限流）
- 两种模式共存：人工触发模式保持不变，Orchestra 作为可选自动化层

## 讨论点

1. **触发标签约定**：用 `orchestra:ready` 触发 dispatch 是否合适？还是用 issue 状态字段？
2. **并发上限**：默认 `max_concurrent_agents: 3` 是否合理？
3. **Linear 支持**：Phase 1 只做 GitHub Issues，Linear 放 Phase 2 还是按需？
4. **Daemon 管理**：后台轮询进程用 systemd service 还是其他方式？

## 参考

- [openai/symphony SPEC.md](https://github.com/openai/symphony/blob/main/SPEC.md)
- [Harness Engineering（Symphony 背后的工程实践）](https://zakelfassi.com/blog/the-harness)
- 本项目 PRD：`docs/v3/orchestra/prd-orchestra-integration.md`
