# Vibe3 Worktree Ownership Standard

> **文档定位**：定义 vibe3 各执行层的 worktree 所有权语义，以及 `cwd` 与 `--worktree` 参数的互斥规则。
> **适用范围**：所有涉及 agent dispatch、codeagent-wrapper 调用、worktree 管理的代码路径。
> **权威性**：本文件是 worktree 所有权与调度语义的唯一权威来源。实现细节以代码为准，架构意图以本文件为准。

---

## 一、核心规则

**`cwd` 与 `--worktree` 互斥**。

- 传递了显式 `cwd` → 禁止同时传递 `--worktree`
- 传递了 `--worktree` → `cwd` 必须为 `None`
- 两者同时存在 → bug，必须修复

原理：`--worktree` 让 codeagent-wrapper 在当前工作目录下创建新 worktree。若 `cwd` 已是某个预分配 worktree，则会在 worktree 内部再嵌套一层 worktree，导致路径混乱。

---

## 二、五层架构 Worktree 语义

```
L0  Orchestra / Heartbeat          -- 调度主循环，无 agent dispatch
L1  Governance Service             -- 只操作 GitHub labels，无代码修改
L2  Supervisor + Apply             -- 读取代码验证，需要 repo 路径
L3  Manager / Plan / Run / Review  -- 代码开发核心，WorktreeManager 预分配
L4  Human collaboration            -- vibe-new 流程，人工引导
```

### L0 — Orchestra / Heartbeat

- 职责：调度主循环（tick），分发 L1/L2/L3 任务。
- Worktree：**不需要**。Orchestra 本身不执行代码修改，不调用 codeagent-wrapper。
- 参数要求：无 cwd，无 --worktree。

### L1 — Governance Service

- 职责：扫描仓库状态（LOC、标签、规则合规），向 GitHub issue 写入治理结论，更新 labels。
- Worktree：**不需要**。Governance 只读取文件、操作 GitHub API，不修改代码。
- 参数要求：`cwd=None`，无 --worktree。可在主仓库路径或任意目录执行。
- 实现位置：`src/vibe3/orchestra/services/governance_service.py`

### L2 — Supervisor + Apply

- 职责：SupervisorHandoffService 读取 `supervisor+state/handoff` issue，验证 findings，执行修正动作（可能修改代码）。
- Worktree：需要 **主仓库路径**（`cwd=repo_path`），无需独立 worktree。
  - Supervisor apply 验证代码但通常不开新功能分支，直接在主仓库执行。
  - 若将来需要隔离，可通过 WorktreeManager 预分配（但这是 L3 的模式，当前 L2 不适用）。
- 参数要求：`cwd=self._manager.repo_path`，禁止 `--worktree`。
- 实现位置：`src/vibe3/orchestra/services/supervisor_handoff.py`
- **当前 bug**：`agent_resolver.py:65` 传递了 `worktree=True`，应改为 `cwd=repo_path`（待修复，见 §四）。

### L3 — Manager / Plan / Run / Review

这是 worktree 管理最复杂的一层，分两个子阶段：

#### L3a — Manager Agent 启动

- 职责：WorktreeManager 在 dispatch 前为 manager agent 预分配 worktree。
- Worktree 分配者：**WorktreeManager**（`src/vibe3/manager/worktree_manager.py`）。
- 参数要求：`cwd=manager_worktree_path`，禁止 `--worktree`。
- WorktreeManager 的 worktree 已包含：
  - 独立的 git worktree（与主仓库隔离）
  - 正确的 branch checkout
  - 环境变量与 flow 状态绑定

#### L3b — Manager Agent 内部派发 Workers

- 职责：Manager agent 运行中通过 `vibe3 run` / `vibe3 plan` 派发 worker agents。
- Worktree 继承：Worker 继承 Manager 的 worktree（通过 `cwd` 透传）。
- **关键约束**：Worker dispatch 命令里 **禁止** 携带 `--worktree`。
  - Manager agent 的 `cwd` 已是 pre-allocated worktree。
  - 若 worker 再加 `--worktree`，会在 worktree 内嵌套创建 `do-<n>` 子目录，导致路径嵌套 bug。
- 实现位置（有 bug 待修）：
  - `src/vibe3/manager/prompts.py:63-64` — `use_worktree` 条件注入 `--worktree` 到 worker cmd
  - `src/vibe3/manager/command_builder.py:50-51` — PR review dispatch 同样有此问题

### L4 — Human Collaboration

- 职责：人工通过 `/vibe-new` 进入开发流程，可选择使用 worktree 或直接 checkout。
- Worktree：由人工或 skill 决定，不强制要求。
- 参数要求：视人工选择而定，与自动化链路无关。

---

## 三、Worktree 所有权表

| 层级 | 执行主体 | Worktree 需求 | 分配者 | 传递方式 | --worktree 使用 |
|------|---------|-------------|-------|---------|---------------|
| L0 | Orchestra/HB | 无 | - | - | 禁止 |
| L1 | GovernanceService | 无 | - | cwd=None | 禁止 |
| L2 | SupervisorHandoffService | repo 路径 | 调用方 | cwd=repo_path | 禁止 |
| L3a | Manager Agent | 独立 worktree | WorktreeManager | cwd=wt_path | 禁止 |
| L3b | Worker Agent | 继承 Manager | 继承 cwd | cwd 透传 | **严禁** |
| L4 | 人工 | 可选 | 人工 | 视情况 | 允许 |

---

## 四、已知 Bug 清单（待修复）

以下问题已通过分析确认，修复方案属于代码重构范畴，在独立 branch 处理：

| 位置 | 问题 | 修复方向 |
|------|------|---------|
| `manager/prompts.py:63-64` | Worker dispatch cmd 含 `--worktree`，与 manager cwd 同时存在 | 移除 `--worktree` 注入逻辑 |
| `manager/command_builder.py:50-51` | PR review dispatch 同样含 `--worktree` | 移除 `use_worktree` 条件分支 |
| `orchestra/agent_resolver.py:65` | supervisor apply 传 `worktree=True`，应传 `cwd=repo_path` | 改为 `cwd=self._manager.repo_path` |
| `orchestra/agent_resolver.py:45` | governance 传 `worktree=True`，governance 无需 worktree | 改为 `worktree=False` 或移除 |
| `manager/manager_executor.py:184` | `worktree=is_temporary` 错误地将临时标志传给 --worktree 参数 | 解耦 is_temporary 与 worktree 参数语义 |

---

## 五、决策原则

### 5.1 分配时机

Worktree 必须在 dispatch 前完成分配，不得在 codeagent-wrapper 内部动态创建（当 cwd 已提供时）。

### 5.2 所有权边界

Worktree 的创建者负责其生命周期管理（创建、绑定 flow、清理）。WorktreeManager 是 L3 链路的唯一合法分配者。

### 5.3 错误处理

若 `cwd` 与 `--worktree` 同时出现，应在调用 codeagent-wrapper 前抛出明确错误，而不是静默执行导致嵌套。建议在 `codeagent.py` 的 `start_async_command` 中添加防御性检查。

### 5.4 验证方式

```bash
# 检查当前 worktree 列表
git worktree list

# 确认无嵌套 worktree（不应在 .git/worktrees/ 子目录下再出现 .git）
find . -name ".git" -type f | grep -v "^./.git$" | head -20
```

---

## 六、与其他标准的关系

- **[vibe3-orchestra-runtime-standard.md](vibe3-orchestra-runtime-standard.md)**：定义 driver/tick/async child 架构，本文件补充其 worktree 语义。
- **[vibe3-state-sync-standard.md](vibe3-state-sync-standard.md)**：定义 flow 状态机，worktree 生命周期与 flow 状态绑定。
- **[agent-debugging-standard.md](agent-debugging-standard.md)**：调试手册，§5.3 apply 步骤以本文件语义为准。
- **[agent-workflow-standard.md](agent-workflow-standard.md)**：Agent 工作流规范，`cwd` 参数传递细节参考本文件。
