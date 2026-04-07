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
L0  Orchestra / Heartbeat          -- 调度主循环，StateLabelDispatchService 负责所有 dispatch
L1  Governance Service             -- 只操作 GitHub labels，无代码修改
L2  Supervisor + Apply             -- 轻量治理执行，临时 worktree 隔离
L3  Manager / Plan / Run / Review  -- 代码开发核心，WorktreeManager 预分配 worktree
L4  Human collaboration            -- vibe-new 流程，人工引导
```

### L0 — Orchestra / Heartbeat

- 职责：调度主循环（tick）。`StateLabelDispatchService` 监听 issue state labels，触发 manager/plan/run/review 四类 dispatch。
- **关键**：**所有** agent dispatch（包括 plan/run/review）都由 `StateLabelDispatchService.on_tick()` 发起，不是 manager agent 发起。
  - `manager` 触发器：检测 `state/ready` 或 `state/handoff` label → dispatch manager agent
  - `plan` 触发器：检测 `state/plan` label → dispatch planner agent
  - `run` 触发器：检测 `state/run` label → dispatch executor agent
  - `review` 触发器：检测 `state/review` label → dispatch reviewer agent
- Worktree：**不需要**。Orchestra 本身不执行代码修改，不调用 codeagent-wrapper 直接。
- 实现位置：`src/vibe3/orchestra/services/state_label_dispatch.py`（`StateLabelDispatchService`）

### L1 — Governance Service

- 职责：扫描仓库状态（LOC、标签、规则合规），向 GitHub issue 写入治理结论，更新 labels。
- Worktree：**不需要**。Governance 只读取文件、操作 GitHub API，不修改代码。
- 参数要求：`cwd=None`，无 --worktree。可在主仓库路径或任意目录执行。
- 实现位置：`src/vibe3/orchestra/services/governance_service.py`

### L2 — Supervisor + Apply

- 职责：`SupervisorHandoffService` 读取 `supervisor+state/handoff` issue，dispatch apply agent 执行治理动作。
- Apply agent 能力范围：
  - 更改 issue labels、关闭 issue、写入 comment
  - 简单文档修正（typo、补漏）
  - 参数配置调整（非代码逻辑）
  - **超出范围的复杂代码改动** → 创建正式 task issue（含 spec），交由 L3 manager 链条处理
- Worktree：需要**临时隔离 worktree**。Apply agent 可能修改文档/配置，需要独立于主仓库的安全空间。
- 参数要求：传递 `--worktree`（由 codeagent-wrapper 自动创建临时 worktree），`cwd=None`。
- 实现位置：`src/vibe3/orchestra/services/supervisor_handoff.py`
- **当前状态**：`agent_resolver.py:65` 已传 `worktree=True`，方向正确，但 cwd 处理需确认（待代码重构 branch）。

### L3 — Manager / Plan / Run / Review

- **Manager agent 是状态机，不是 dispatcher**。Manager agent 读取 issue 上下文，执行状态流转（例如将 `state/ready` 改为 `state/plan`）。后续的 plan/run/review 由 L0 的 `StateLabelDispatchService` 检测到标签变化后触发。
- **所有 L3 agents 均由 `StateLabelDispatchService` dispatch**，并通过 `WorktreeManager.resolve_manager_cwd()` 解析 worktree 路径。

#### L3 dispatch 流程

```
StateLabelDispatchService.on_tick()
  → _resolve_cwd() → WorktreeManager.resolve_manager_cwd()
  → start_async_command(cmd, cwd=wt_path)
```

- Worktree 分配者：**WorktreeManager**（`src/vibe3/manager/worktree_manager.py`）。
- 参数要求：`cwd=wt_path`，禁止 `--worktree`。
- WorktreeManager 的 worktree 已包含：
  - 独立的 git worktree（与主仓库隔离）
  - 正确的 branch checkout
  - 环境变量与 flow 状态绑定

#### 关于 prompts.py 中 --worktree 的说明

`manager/prompts.py:63-64` 和 `command_builder.py:50-51` 中仍有 `--worktree` 注入逻辑。这些路径属于 CLI 直接调用路径（非 orchestra path）或遗留的 prompt 模板内容，不代表 manager agent 会在运行中 dispatch workers。这些 `--worktree` 注入在 orchestra 路径下会导致 bug（详见 §四）。

### L4 — Human Collaboration

- 职责：人工通过 `/vibe-new` 进入开发流程，可选择使用 worktree 或直接 checkout。
- Worktree：由人工或 skill 决定，不强制要求。
- 参数要求：视人工选择而定，与自动化链路无关。

---

## 三、Worktree 所有权表

| 层级 | 执行主体 | Dispatch 来源 | Worktree 需求 | 传递方式 | --worktree 使用 |
|------|---------|-------------|-------------|---------|---------------|
| L0 | StateLabelDispatchService | 自身（tick loop） | 无 | - | 禁止 |
| L1 | GovernanceService | StateLabelDispatch | 无 | cwd=None | 禁止 |
| L2 | SupervisorHandoffService | SupervisorHandoff.on_tick | 临时 worktree | --worktree | 允许（隔离用） |
| L3 | Manager Agent | StateLabelDispatch | 独立 worktree | cwd=wt_path | 禁止 |
| L3 | Plan/Run/Review Agent | StateLabelDispatch | 独立 worktree | cwd=wt_path | 禁止 |
| L4 | 人工 | 人工触发 | 可选 | 视情况 | 允许 |

---

## 四、已知 Bug 清单（待修复）

以下问题已通过分析确认，修复方案属于代码重构范畴，在独立 branch 处理：

| 位置 | 问题 | 修复方向 |
|------|------|---------|
| `manager/prompts.py:63-64` | CLI 路径中 dispatch cmd 携带 `--worktree`，而调用环境已有 cwd（worktree 嵌套） | 移除 `--worktree` 注入逻辑（CLI 路径统一通过 cwd 传递） |
| `manager/command_builder.py:50-51` | PR review dispatch 同样携带 `--worktree` | 移除 `use_worktree` 条件分支 |
| `orchestra/agent_resolver.py:45` | governance resolve 传 `worktree=True`，governance 无需 worktree | 改为 `worktree=False` 或移除 |
| `orchestra/agent_resolver.py:65` | supervisor apply 传 `worktree=True` 但 cwd 处理不清晰 | 确认 `--worktree` 路径通 → `cwd=None`；需与 `SupervisorHandoffService` 调用侧对齐 |
| `manager/manager_executor.py:184` | `worktree=is_temporary` 将临时标志误传给 --worktree 参数 | 解耦 is_temporary 与 worktree 参数语义 |

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
