# Vibe3 Worktree Ownership Standard

> **文档定位**：定义 vibe3 各执行层的 worktree 所有权语义与路径解析规则。
> **适用范围**：所有涉及 agent dispatch、codeagent-wrapper 调用、worktree 管理的代码路径。
> **权威性**：本文件是 worktree 所有权与调度语义的唯一权威来源。实现细节以代码为准，架构意图以本文件为准。

---

## 一、核心原则

### 1.1 自动路径管理
Vibe 3.0 实现了 Worktree 的自动化管理。**用户和调用者无需通过 `--worktree` 标志手动请求隔离环境**，系统会根据任务上下文自动解析并锁定最佳执行路径（CWD）。

- **系统负责隔离**：Orchestra 会自动为 Issue 准备专用的持久 Worktree，或为临时任务准备临时 Worktree。
- **透明执行**：后端执行器（codeagent-wrapper）始终在系统预设好的 `cwd` 中运行，不再承担“自动创建 worktree”的职责。

### 1.2 Worktree 身份与生命周期
- **持久 Worktree (Issue-bound)**：与 GitHub Issue 绑定，生命周期贯穿 `claimed -> handoff`。由 `WorktreeManager.acquire_issue_worktree()` 确保其唯一性。
- **临时 Worktree (Task-bound)**：用于 L2 治理、PR 审查等短期任务，由 `WorktreeManager.acquire_temporary_worktree()` 管理，任务结束后可被回收。

---

## 二、各层级语义定义

### L0 — Orchestra / Heartbeat

- 职责：调度主循环（tick）。`StateLabelDispatchService` 监听状态并触发 dispatch。
- **自动隔离逻辑**：在派发 L3 Agents 之前，系统会检查该任务是否需要独立路径。若需要，由 `WorktreeManager` 提前准备好物理路径。
- **事件驱动协同**：Agent 发布领域事件（如 `PlanCompleted`），处理器根据事件更新状态，Orchestra 随后在下一轮 tick 中根据新状态再次自动解析路径进行后续调度。

### L1 — Governance Service

- 职责：扫描仓库状态。
- 路径：通常在主仓库路径执行，不需要独立 worktree。

### L2 — Supervisor + Apply

- 职责：执行治理动作。
- **自动隔离**：系统会自动为其分配临时隔离路径（Temporary Worktree），防止治理动作（如补丁应用、配置修正）污染主仓库环境。

### L3 — Manager / Plan / Run / Review

- **统一路径解析**：所有 L3 任务均由系统根据关联的 Issue 编号自动锁定对应的 `issue-worktree` 路径。
- **Manager (状态机)**：负责发布状态迁移事件。
- **执行 Agent (Plan/Run/Review)**：由系统直接调度到已准备好的 worktree 中执行。

---

## 三、参数规范（清理后）

### 3.1 废弃参数说明
- **彻底移除 `--worktree` 标志**：该标志不再出现在 CLI 选项中。系统不再需要用户手动告知“是否需要 worktree”，而是根据 Role 和 Context 自动决策。
- **彻底移除 `--sync` 标志**：系统默认为异步执行模式。同步模式仅作为调试用的底层能力，不再向正常工作流暴露标志。

### 3.2 显式 CWD 传递
在系统内部调用链路中，必须传递解析后的 `cwd` 物理路径。这是因为：
1.  **路径确定性**：确保后端执行器准确落在预分配的隔离区。
2.  **避免嵌套**：系统已处理好路径，后端直接使用即可，严禁后端再次尝试创建路径。

---

## 四、变更历史

| 版本 | 日期 | 变更说明 |
| :--- | :--- | :--- |
| 1.0 | 2026-04-05 | 初始版本，定义调度语义 |
| 1.2 | 2026-04-08 | **参数内部化清理**：移除 --worktree 与 --sync 标志，确立“系统自动管理隔离路径”原则 |

---

**相关文档**：
- **[vibe3-event-driven-standard.md](vibe3-event-driven-standard.md)**：定义事件驱动如何触发上述调度。
- **[vibe3-state-sync-standard.md](vibe3-state-sync-standard.md)**：定义 Worktree 生命周期与 Issue 状态的绑定关系。
