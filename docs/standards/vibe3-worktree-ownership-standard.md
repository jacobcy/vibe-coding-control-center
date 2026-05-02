# Vibe3 Worktree Ownership Standard

> **文档定位**：定义 vibe3 各执行层的 worktree 所有权语义，以及路径自动解析规则。
> **适用范围**：所有涉及 agent dispatch、codeagent-wrapper 调用、worktree 管理的代码路径。
> **权威性**：本文件是 worktree 所有权与调度语义的唯一权威来源。实现细节以代码为准，架构意图以本文件为准。

---

## 一、核心原则

### 1.1 自动路径管理
Vibe 3.0 实现了隔离路径的自动化管理。系统根据 Role 和 Context 自动解析物理路径，**不再依赖并移除 `--worktree` 参数**。

### 1.2 路径确定性
- **控制侧**：Orchestra 必须在 dispatch 之前通过 `WorktreeManager` 完成路径锁定（持久 issue-worktree 或临时 temporary worktree）。
- **执行侧**：后端执行器（codeagent-wrapper）始终在系统预设好的 `cwd` 中运行，禁止后端再次动态创建工作树。

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
- **事件驱动协同**：Agent 执行完成或失败时发布领域事件（见 [vibe3-event-driven-standard.md](vibe3-event-driven-standard.md)），由事件处理器负责更新 GitHub labels。Orchestra 的 tick 循环作为“外部观察者”消费这些 label 变迁并触发下一阶段 dispatch。
- Worktree：**不需要**。Orchestra 本身不执行代码修改，不调用 codeagent-wrapper 直接。
- 实现位置：`src/vibe3/orchestra/services/state_label_dispatch.py`（`StateLabelDispatchService`）

### L1 — Governance Service

- 职责：按治理材料执行观察、纳入与派单。
- `assignee-pool governance`：观察 assignee issue pool 状态，输出排序 / 建议 / 最小纠偏。
- `roadmap governance`：扫描 broader repo issue pool，把适合自动化推进的 bug fix / small feature 纳入 assignee issue pool。
- `cron governance`：周期性挑选过时文档，创建或更新 supervisor issue，交由 L2 apply 处理。
- Worktree：**不需要**（`WorktreeRequirement.NONE`）。Governance 是周期扫描观察，只读取文件、操作 GitHub API，不修改代码，无临时 worktree。
- 参数要求：`cwd=None`。可在主仓库路径或任意目录执行。禁止使用已移除的 `--worktree` 标志。
- 实现位置：`src/vibe3/orchestra/services/governance_service.py`

### L2 — Supervisor + Apply

- 职责：`SupervisorHandoffService` 读取 `supervisor+state/handoff` issue，dispatch apply agent 执行治理动作。发布 `SupervisorApplyDispatched` 等事件。
- Apply agent 能力范围：
  - 更改 issue labels、关闭 issue、写入 comment
  - 在核查后关闭旧 issue 并创建 replacement issue（仅 GitHub 治理动作，不等于代码实现）
  - 文档类修改（语义对齐、校正、格式修补）
  - 测试修补类修改（仅限测试文件与测试夹具）
  - 对上述 L2 改动可直接 commit / push / pr create
  - **超出范围的主代码改动或复杂验证** → 创建正式 task issue（含 spec），交由 L3 manager 链条处理
- 治理语义：
  - `dev/issue-*` 是主线开发承载面
  - `task/issue-*` 是自动化承载面
  - 当 `task/issue-*` 现场被旧 PR / 旧 flow / 错误状态污染时，允许 supervisor 直接做 issue 级治理；不要因为“apply”二字就默认只能观察
- Worktree：需要**临时隔离 worktree**（`WorktreeRequirement.TEMPORARY`）。Apply agent 可能修改文档或测试，需要独立于主仓库的安全空间。与 governance scan 不同：apply 是执行治理动作，需要 worktree；governance 是扫描观察，不需要 worktree。
- 注意：当前实现即使只做 issue/label/comment/close 动作，也仍可能统一分配临时 worktree；这不代表 apply 自动获得代码修改职责，也不意味着所有治理动作都必须转成实现任务。
- 参数要求：`cwd=wt_path`（由系统自动分配临时隔离路径）。禁止使用已移除的 `--worktree` 标志。
- 实现位置：`src/vibe3/orchestra/services/supervisor_handoff.py`
- **当前状态**：`agent_resolver.py:65` 已传 `worktree=True`，方向正确，但 cwd 处理需确认（待代码重构 branch）。

### L3 — Manager / Plan / Run / Review

- **Manager agent 是状态机，不是 dispatcher**。Manager agent 读取 issue 上下文，决定状态流转意图并发布事件（如 `IssueStateChanged` 或 `ManagerExecutionCompleted`）。后续的 plan/run/review 由 L0 的 `StateLabelDispatchService` 检测到由事件处理器更新的标签变化后触发。
- **所有 L3 agents 均由 `StateLabelDispatchService` dispatch**，并通过 `WorktreeManager.resolve_manager_cwd()` 解析 worktree 路径。

#### L3 dispatch 流程

```
StateLabelDispatchService.on_tick()
  → _resolve_cwd() → WorktreeManager.resolve_manager_cwd()
  → start_async_command(cmd, cwd=wt_path)
```

- Worktree 分配者：**WorktreeManager**（`src/vibe3/environment/worktree.py`）。
- 参数要求：`cwd=wt_path`（锁定 issue-worktree）。禁止使用已移除的 `--worktree` 标志。
- WorktreeManager 的 worktree 已包含：
  - 独立的 git worktree（与主仓库隔离）
  - 正确的 branch checkout
  - 环境变量与 flow 状态绑定

#### 关于 prompts.py 中 --worktree 的清理
`manager/prompts.py` 和 `command_builder.py` 中的 `--worktree` 注入逻辑已被彻底移除。现在所有派发路径统一通过显式 `cwd` 传递，不再在 prompt 模板中混合环境指令。

### L4 — Human Collaboration

- 职责：人工通过 `/vibe-new` 进入开发流程，可选择使用 worktree 或直接 checkout。
- Worktree：由人工或 skill 决定，不强制要求。
- 参数要求：视人工选择而定，与自动化链路无关。

---

## 三、Worktree 所有权表

| 层级 | 执行主体 | Dispatch 来源 | Worktree 需求 | 传递方式 | --worktree 使用 |
|------|---------|-------------|-------------|---------|---------------|
| L0 | StateLabelDispatchService | 自身（tick loop） | 无 | - | 禁止（已移除） |
| L1 | GovernanceService | StateLabelDispatch | 无 | cwd=None | 禁止（已移除） |
| L2 | SupervisorHandoffService | SupervisorHandoff.on_tick | 临时 worktree | cwd=wt_path | 禁止（已移除） |
| L3 | Manager Agent | StateLabelDispatch | 独立 worktree | cwd=wt_path | 禁止（已移除） |
| L3 | Plan/Run/Review Agent | StateLabelDispatch | 独立 worktree | cwd=wt_path | 禁止（已移除） |
| L4 | 人工 | 人工触发 | 可选 | 视情况 | 废弃 |

---

## 四、已知 Bug 清单（待修复）

以下问题已在 `refactor/internal-run` 分支中通过代码重构修复：

| 位置 | 问题 | 修复结果 |
|------|------|---------|
| `manager/prompts.py` | CLI 路径注入 `--worktree` 导致嵌套 | **已移除** 注入逻辑，统一通过 `cwd` 传递 |
| `manager/command_builder.py` | PR review dispatch 携带 `--worktree` | **已移除** `use_worktree` 分支，改为自管理路径 |
| `orchestra/agent_resolver.py` | governance/supervisor 误传 `worktree=True` | **已删除** `AgentOptions.worktree` 字段，参数彻底移除 |
| `manager/manager_executor.py` | 误传临时标志给 `--worktree` 参数 | **已解耦**，不再向后端传递任何隔离标志 |

---

## 五、决策原则

### 5.1 分配时机

Worktree 必须在 dispatch 前完成分配，不得在 codeagent-wrapper 内部动态创建（当 cwd 已提供时）。

### 5.2 所有权边界

Worktree 的创建者负责其生命周期管理（创建、绑定 flow、清理）。WorktreeManager 是 L3 链路的唯一合法分配者。

### 5.3 错误处理

由于 `--worktree` 参数已被移除，嵌套 worktree 的风险已通过“单点路径分配（WorktreeManager）”在架构上规避。
- 严禁在 backend 调用中尝试二次创建路径。
- 系统默认使用异步模式（Async），同步模式（Sync）仅限底层调试，不再作为业务参数传递。

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
- **[v3/command-standard.md](v3/command-standard.md)**：定义 flow 状态机，worktree 生命周期与 flow 状态绑定。
- **[agent-debugging-standard.md](agent-debugging-standard.md)**：调试手册，§5.3 apply 步骤以本文件语义为准。
- **[agent-workflow-standard.md](agent-workflow-standard.md)**：Agent 工作流规范，`cwd` 参数传递细节参考本文件。
