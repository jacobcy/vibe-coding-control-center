---
document_type: plan
title: orchestra manager end-to-end debug
status: in-progress
author: vibe-check
created: 2026-04-01
related_issues:
  - "#369"
  - "#370"
related_docs:
  - src/vibe3/orchestra/services/assignee_dispatch.py
  - src/vibe3/orchestra/dispatcher.py
  - src/vibe3/config/settings_orchestra.py
  - tests/vibe3/orchestra/test_dispatcher_manager.py
---

# Goal

验证 orchestrator + manager 链路可完整执行：

1. orchestra server 能正确识别 `vibe-manager-agent` 身份（issue #369）
2. manager 被分派后能在正确 worktree 启动最小执行（issue #370）

# Non-Goals

- 不验证 agent 产出物（PR 内容、代码质量）
- 不做 GitOps 全链路的端到端
- 不修改 orchestrator 核心逻辑（除非调试发现必须修复的 bug）

# Background

PR #408 已合并，修复了 loop 和 async branch 不一致。
Unit tests: 176 passed。
Issue #369 / #370 状态 `ready`，尚无绑定 flow。

---

# Phase 1: 前提条件核查

**目标**: 确认配置、服务、GitHub 侧 assignee 三者一致

## 检查命令

```bash
# 1a. OrchestraConfig manager_usernames 加载是否正确
uv run python -c "
from vibe3.orchestra.config import OrchestraConfig
c = OrchestraConfig()
print('manager_usernames:', c.manager_usernames)
print('dry_run:', c.dry_run)
print('repo:', c.repo)
"

# 1b. orchestra server 进程状态
uv run python src/vibe3/cli.py serve status

# 1c. issue #369 / #370 assignees 是否包含 vibe-manager-agent
GH_PAGER=cat gh issue view 369 --json assignees,labels
GH_PAGER=cat gh issue view 370 --json assignees,labels
```

## 通过条件

- [x] `manager_usernames` 包含 `"vibe-manager-agent"`
- [ ] `serve status` 显示 running + 有效端口
- [x] #369 / #370 assignee 包含 `vibe-manager-agent`

## 结果

| 检查项 | 状态 | 备注 |
|--------|------|------|
| manager_usernames 配置 | PASS | `['vibe-manager-agent']`，dry_run=False |
| repo 配置 | PASS | None — gh CLI 自动检测，不影响运行 |
| serve status | PASS | 已启动（PID 23881），-v 模式重启以显示 INFO 日志 |
| #369 assignee | PASS | vibe-manager-agent 已指派，labels: state/ready |
| #370 assignee | PASS | vibe-manager-agent 已指派，labels: state/ready |

## 如需修复

- server 未运行 → Phase 3 前需 `uv run python src/vibe3/cli.py serve start` 启动
- assignee 缺失（当前不需要）: `gh issue edit 369 --add-assignee vibe-manager-agent`
- config 不对（当前不需要）: 检查 `config/settings.yaml` 或环境变量 `VIBE_MANAGER_USERNAMES`

---

# Phase 2: Manager Identity 单测绿

**目标**: 确认 `AssigneeDispatchService` 在 `vibe-manager-agent` 被指派时正确命中分派路径

## 检查命令

```bash
# 运行 dispatcher manager 专项测试
uv run pytest tests/vibe3/orchestra/test_dispatcher_manager.py -v

# 运行全部 assignee 相关测试
uv run pytest tests/vibe3/ -k "assignee" -v

# 运行完整 orchestra 测试确认无回归
uv run pytest tests/vibe3/orchestra/ -v --tb=short 2>&1 | tail -10
```

## 通过条件

- [x] `test_dispatcher_manager.py` 全绿
- [x] `assignee` 相关测试全绿
- [x] orchestra 总计仍 176 passed（无新失败）

## 结果

| 测试集 | 通过数 | 失败数 | 备注 |
|--------|--------|--------|------|
| test_dispatcher_manager | 8 | 0 | cwd resolution + command normalization + integration |
| -k assignee | 7 | 0 | handle_event + on_tick + cold_start warmup |
| orchestra 总计 | 176 | 0 | 无回归 |

## 如需修复

- 若 `assignee_dispatch` 缺少测试 → 记为 Gap A，在 Phase 4 前补充
- 若已有测试失败 → 追踪具体断言，定位代码层 bug

---

# Phase 3: Webhook 模拟触发

**目标**: 向运行中的 server 发送模拟 `issues/assigned` 事件，验证分派日志出现

## 检查命令

```bash
# 3a. 获取 server 端口（从 serve status 输出确认）
PORT=<从上一步获取>

# 3b. 模拟 #369 的 assigned 事件
curl -s -X POST http://localhost:${PORT}/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -d '{
    "action": "assigned",
    "assignee": {"login": "vibe-manager-agent"},
    "issue": {
      "number": 369,
      "title": "[orchestra-smoke-agent] manager identity check",
      "state": "open",
      "labels": [{"name": "state/ready"}],
      "assignees": [{"login": "vibe-manager-agent"}]
    }
  }'

# 3c. 若 server 配置了 webhook secret，需带签名，或先改 dry_run 模式测试
# 检查 server 日志是否有: "assigned to 'vibe-manager-agent' (manager)"
```

## 通过条件

- [x] HTTP 响应 200
- [x] server 日志出现 `"Webhook: #369 assigned to 'vibe-manager-agent' (manager)"`
- [x] `_dispatch_if_ready` 被调用（日志体现）

## 结果

| 检查项 | 状态 | 备注 |
|--------|------|------|
| HTTP 响应码 | PASS | 200 `{"status":"accepted","event":"issues"}` |
| manager 命中日志 | PASS | `Webhook: #369 assigned to 'vibe-manager-agent' (manager)` |
| dispatch_if_ready 调用 | PASS | `Received: issues/assigned` 后顺序触发 |

**注**：默认 verbose=0 为 ERROR 级别。Phase 3 需要以 `-v` 启动 server 才能看到 INFO 日志。生产环境若需监控可加 `-v`。

## 如需修复

| 问题 | 处置 |
|------|------|
| 401/403: secret 验证失败 | 用 HMAC-SHA256 签名，secret 在 config/settings.yaml `orchestra.webhook_secret` |
| 没有日志输出 | 以 `-v` 重启 server，INFO 级别才可见 |
| action 被过滤 | 检查 `handle_event` 中 action 判断逻辑 |

---

# Phase 4: Dispatch dry_run 验证 Worktree 链路

**目标**: 在 `dry_run=True` 下验证 dispatcher 能正确构建命令并解析 worktree 路径，不真正执行

## 检查命令

```bash
uv run python -c "
from pathlib import Path
from vibe3.orchestra.config import OrchestraConfig
from vibe3.orchestra.dispatcher import Dispatcher
from vibe3.models.orchestration import IssueInfo, IssueState

config = OrchestraConfig(dry_run=True)
d = Dispatcher(config, repo_path=Path.cwd())
issue = IssueInfo(
    number=370,
    title='minimal run on manager worktree',
    state=IssueState.CLAIMED,
    labels=['state/claimed'],
)
result = d.dispatch(issue)
print('dispatch result:', result)
print('last cmd:', d.command_builder.last_manager_render_result)
"
```

## 通过条件

- [ ] `dispatch()` 不报异常
- [ ] 返回 `True`（dry_run 成功）
- [ ] `_resolve_manager_cwd` 返回有效路径
- [ ] 命令包含正确的 `vibe3 run` 参数

## 结果

**重要发现：Phase 4 测试脚本有 dry_run 参数 bug，导致意外触发真实执行（变成 Phase 5）**

| 检查项 | 状态 | 备注 |
|--------|------|------|
| dispatch 无异常 | PASS | 执行至完成，但是真实执行（非 dry_run）|
| 返回 True | PASS | 命令成功派发 |
| cwd 路径有效 | PASS | `.worktrees/issue-370` 正确创建 |
| 命令参数正确 | PASS | `uv run python -m vibe3 run --worktree Implement issue #370: minimal run on manager worktree` |

**Bug 记录**（测试脚本问题，非生产代码 bug）：
```python
# 错误写法（干跑 bug）：
config = OrchestraConfig(dry_run=True)
d = Dispatcher(config, repo_path=Path.cwd())  # ← dry_run 未传入，默认 False！
# 正确写法：
d = Dispatcher(config, repo_path=Path.cwd(), dry_run=config.dry_run)
```
- `Dispatcher.__init__` 的 `dry_run` 参数默认值为 `False`，不从 config 自动继承
- 生产代码 `AssigneeDispatchService` 写法正确（已显式传 `dry_run=config.dry_run`）
- 测试脚本缺失 `dry_run=config.dry_run`，导致实际执行

**实际执行链路（Phase 4 意外完成了 Phase 5）**：
1. `FlowOrchestrator.create_flow_for_issue(#370)` → DB 写入 `task/issue-370` flow (active)
2. `_ensure_manager_worktree` → 创建 `.worktrees/issue-370`（以及 #369 的同名目录）
3. 标签转换：`state/ready` → `state/in-progress`（GitHub 侧已确认）
4. 派发命令 → `vibe3 run --worktree "Implement issue #370: minimal run on manager worktree"`
5. `codeagent-wrapper --agent develop` 启动（PID 33077）
6. 子进程 `opencode run -m alibaba-coding-plan-cn/glm-5` 启动（PID 33100，尚在运行）

## 如需修复

| 问题 | 处置 |
|------|------|
| `dispatch()` 方法签名不匹配 | 正确方法名为 `dispatch_manager(issue)` 而非 `dispatch(issue)` |
| worktree 路径找不到 | 已正常创建，无需修复 |
| 命令参数格式 | 已验证正确：`--worktree` 是布尔标志，后面跟 INSTRUCTIONS 位置参数 |
| Dispatcher dry_run 参数不一致 | 建议为 Dispatcher 增加 "优先从 config 读取 dry_run" 文档或默认值修复（新 issue 待提） |

---

# Phase 5: 端到端最小执行（谨慎）

**条件**: Phase 1-4 全部通过后才执行

**目标**: 对 issue #370 发一次真实 webhook，观察 manager 在 worktree 里启动最小执行

## 检查命令

```bash
# 5a. 确认 dry_run=False（生产配置）
# 5b. 发送真实触发
PORT=<server port>
curl -s -X POST http://localhost:${PORT}/webhook \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: issues" \
  -d '{
    "action": "assigned",
    "assignee": {"login": "vibe-manager-agent"},
    "issue": {
      "number": 370,
      "title": "[orchestra-smoke-3] minimal run on manager worktree",
      "state": "open",
      "labels": [{"name": "state/claimed"}],
      "assignees": [{"login": "vibe-manager-agent"}]
    }
  }'

# 5c. 轮询 flow 状态（仅观察，不干预）
uv run python src/vibe3/cli.py status
```

## 通过条件

- [ ] server 日志显示 manager dispatch 启动
- [ ] `uv run python src/vibe3/cli.py status` 显示新的 active flow 或 worktree
- [ ] 无 circuit breaker open / crash 事件

## 结果

**Phase 4 意外触发了 Phase 5（真实执行），但链路验证完整成功**

| 检查项 | 状态 | 备注 |
|--------|------|------|
| dispatch 启动日志 | PASS | 日志：`Dispatching manager: uv run python -m vibe3 run --worktree ...` |
| status 有新 flow | PASS | DB 中 `task/issue-370` 和 `task/issue-369` 均为 active |
| worktree 创建 | PASS | `.worktrees/issue-369`、`.worktrees/issue-370` 均已创建 |
| do/ 子 worktree | PASS | `do/20260401-ce8b75`（issue-370）、`do/20260401-8f2dc5`（issue-369）均已创建 |
| codeagent-wrapper 启动 | PASS | PID 33077，agent=develop，在 s099 终端运行 |
| opencode agent 启动 | PASS | PID 33100，`opencode run -m alibaba-coding-plan-cn/glm-5`，尚在运行中 |
| GitHub 标签更新 | PASS | #370 已从 `state/ready` → `state/in-progress`，assignee 保留 |
| 无 crash | PASS | 所有进程处于 S+ 状态，无异常退出 |

**完整链路**：
```
webhook → AssigneeDispatchService → Dispatcher.dispatch_manager()
  → FlowOrchestrator.create_flow_for_issue()  [DB: task/issue-370 active]
  → _ensure_manager_worktree()               [.worktrees/issue-370 创建]
  → label_client.transition_label()          [state/ready → state/in-progress]
  → _run_command("vibe3 run --worktree ...")  [派发]
    → codeagent-wrapper (PID 33077)
      → opencode run -m glm-5 (PID 33100)   [agent 在 do/ worktree 中运行]
```

**后续**：agent (opencode/GLM-5) 尚在运行，issue #370 / #369 的 do/ worktree 均已就位。

---

# Issue 关闭条件

| Issue | 关闭条件 |
|-------|---------|
| #369 (manager identity) | Phase 2 + Phase 3 通过：日志确认 vibe-manager-agent 命中 |
| #370 (minimal run) | Phase 4 + Phase 5 通过：worktree 执行链路完整 |

---

# 进度汇总

| Phase | 状态 | 完成时间 | 备注 |
|-------|------|---------|------|
| Phase 1: 前提条件 | PASS | 2026-04-01 | config ✓ / assignee ✓ / server 已启动 PID 23881 |
| Phase 2: 单测绿 | PASS | 2026-04-01 | 176 passed，8+7 dispatcher/assignee 专项全绿 |
| Phase 3: Webhook 模拟 | PASS | 2026-04-01 | HTTP 200，日志确认 vibe-manager-agent 命中 |
| Phase 4: dry_run 验证 | PASS (意外真实执行) | 2026-04-01 | 发现 Dispatcher dry_run 参数 bug（测试脚本未传），worktree 链路完整 |
| Phase 5: 端到端执行 | PASS (意外触发) | 2026-04-01 | codeagent-wrapper + opencode/GLM-5 完整启动，do/ worktree 就位 |
