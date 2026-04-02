---
document_type: standard
title: Vibe Coding Authorship Standard
status: approved
scope: identity-tracking
authority:
  - agent-authorship
  - multi-agent-collaboration
author: Codex GPT-5 / human
created: 2026-03-08
last_updated: 2026-04-01
related_docs:
  - docs/standards/glossary.md
  - docs/standards/v3/registry-json-standard.md
  - skills/vibe-commit/SKILL.md
---

# Vibe Coding 署名规范 (Authorship Standard)

在 Vibe Coding 的多智能体（Multi-Agent）开发流水线中，一段代码的诞生往往经历了规划（Planning）、执行（Execution）、代码审查（Review）与最终合并（Commit）等多个阶段，由多个不同的 Agent（如 Claude, Gemini, Codex）甚至人类用户共同接力完成。

为了**尊重每个 Agent 的劳动成果**，同时为了在系统出现 Bug 时拥有绝对清晰的**问责与追踪机制（Accountability Track）**，本项目实行严格的**“逻辑署名与物理签名彻底脱钩”**标准。

## 1. 核心概念重申

在系统上下文中，必须绝不混淆以下两个维度的身份标识（详细定义参见 [glossary.md](./glossary.md)）：

*   **物理签名 (Git Author / Physical Signature)**：
    工作在隔离沙盒底层的单一身份标记（即 `.git/config` 中的 `user.name` 和 `user.email`）。
    *约束：* 物理环境不主动记录多人接力历史，它只在最后时刻代表最终物理提交的“操作员”。

*   **逻辑署名 (Authorship / Agent Log)**：
    工作在认知层（Tier 2/3）与数据大盘（Task Registry）中的参与者名单。它是系统层面对各协助者的主动名册化管理。
    *意义：* “如果你改了代码，你就有权且必须在日志中留下你的名字”。

## 2. 行为准则 (The Golden Rules)

### 2.1 禁止被动硬编码署名
**绝对禁止在 `worktree` 的创建和初始化（如底层 `wtnew` 脚本）中，或在 `vibe flow new` 这类现场切换命令中，自动绑定或覆写工作区的底层 Git 物理签名作为任务归属。**

*原因：* Task 是一个跨生命周期的流转体，而不是被某一个具体的 Agent（即被动分配的环境名字）私有的。工作区环境属于基础设施，并不代表逻辑归属。

### 2.2 主动署名 (Active Authorship)
署名必须是由 Skill 层或 Agent 认知层主发起的一种声明，具有宣告性质。此逻辑现在统一由 `SignatureService` 决断并管理（具体包含 Flow 操作优先级的 `resolve_actor` 与用于 UI/PR 展示的 `normalize_actor`）。

每当一个 Agent / Human 接管一个工作区中的 Flow 现场时（例如通过 `--actor` 显式标注或通过后台 Handoff 写入），底层 Flow State（`.git/vibe3/flow_state.json` 或 SQLite 数据库）必须记录/更新各个阶段的认知所有者。

```json
// 数据结构要求：
"flow_state": {
  "planner_actor": "gemini",
  "executor_actor": "claude/sonnet-4.6",
  "reviewer_actor": "jacob",
  "latest_actor": "claude/sonnet-4.6"
}
```

### 2.3 `vibe-save` 与 Handoff 的认知归属
在进行中间态记录 (`/vibe-save` 工作流) 或记录 Handoff 时，Agent 必须将自己的身份显式带入产生的日志条目中，证明该阶段成果（如某个函数的重构思路）是由其负责产出的。系统会自动确保 `latest_actor` 的流转追踪正确落实。

## 3. 最终物化：PR Contributors 与 `Co-authored-by`

为了将逻辑署名（认知财产）最终刻入代码史册，本项目依赖 PR 描述的汇总块与 Git 标准的 Trailer 语法：`Co-authored-by`。

**结算点约束：**
在进行自动草拟 PR 或最终提交代码前，系统（通过 `PRMetadata.contributors`）**必须**执行以下步骤：

1. 聚合当前 Flow 的名册：`planner_actor`、`executor_actor`、`reviewer_actor` 以及 `latest_actor`。
2. 过滤掉所有未发生实际认知贡献的占位符（如 `unknown`, `system`, `workflow` 等）。
3. 使用 `SignatureService.normalize_actor` 标准化签名，并进行后端去重（例如 `Agent-Claude` 和 `claude/sonnet-4.6` 将被聚合成最具体的 `claude/sonnet-4.6`）。
4. 在生成的 PR Body（或 Conventional Commit）中动态拼接这批贡献者。

*正确结项的代码/PR 表现示例：*
```text
Vibe3 Contributors:
- 🤖 claude/sonnet-4.6
- 🤖 gemini
- 👤 jacob
```

---
**结论**：在 Vibe Center 架构下，没有任何一笔 Agent 的代码心血会被磨灭。智能体的劳动拥有可审计的归属权。
