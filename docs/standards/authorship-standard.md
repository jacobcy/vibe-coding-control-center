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
last_updated: 2026-03-08
related_docs:
  - docs/standards/glossary.md
  - docs/standards/v2/registry-json-standard.md
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
署名必须是由 Skill 层或 Agent 认知层主发起的一种声明，具有宣告性质。

每当一个 Agent / Human 接管一个在工作区中的 Task 现场时（如使用 `--agent claude` 唤醒工作区或通过 `vibe flow bind`），底层数据库（`task.json` 的 `agent_log` 字段）必须**追加（Append）**该贡献者的 ID 至执行者名单（`executed_by`），并更新最后活动者（`latest_actor`）。

```json
// 数据结构要求：
"agent_log": {
  "planned_by": "gemini",
  "executed_by": ["gemini", "claude", "jacob"], // 去重追加，保留接力记录
  "committed_by": null,
  "latest_actor": "jacob"
}
```

### 2.3 `vibe-save` 的认知归属
在进行中间态记录 (`/vibe-save` 工作流) 沉淀认知成果时，Agent 必须将自己的身份显式带入产生的日志条目中（例如以 `@Agent-Name:` 开始），证明该阶段成果（如某个函数的重构思路）是由其负责产出的。

## 3. 最终物化：`Co-authored-by` 注入规则

为了将逻辑署名（认知财产）最终刻入代码史册，本项目依赖 Git 标准的 Trailer 语法：`Co-authored-by`。

**`vibe-commit` 结算点限制：**
在自动草拟并最终提交代码（执行 `vibe flow pr` 等打包结项动作）之前，负责结算的 Agent（通常为主编排或 Reviewer Agent，如 Codex）**必须**执行以下步骤：

1.  读取该工单大盘的 `.agent_log.executed_by` 名册数组。
2.  为其中有别于当前执笔者的所有其他协作者，动态生成标准的 Git 署名 Trailer 字符串（排除自己以防冲突）。
    格式：`Co-authored-by: Agent-{Name} <{name}@vibe.coding>`
3.  将其原封不动地拼接至生成的 Conventional Commit 摘要或最后发出的 PR Body 中。

*正确结项的代码历史表现：*
```text
feat: implements the end-to-end multi-agent orchestration

Decoupled physical git signature from logical authorship array.

Co-authored-by: Agent-Gemini <gemini@vibe.coding>
Co-authored-by: Human-Jacob <jacob@vibe.coding>
```

---
**结论**：在 Vibe Center 架构下，没有任何一笔 Agent 的代码心血会被磨灭。智能体的劳动拥有可审计的归属权。
