---
title: "Advanced Tool Use 参考报告"
source: "https://www.anthropic.com/engineering/advanced-tool-use"
author: "Claude Sonnet 4"
date: "2026-02-28"
purpose: "分析 Anthropic 三项高级工具使用特性，评估在 Vibe Center 项目中的应用潜力"
---

# Advanced Tool Use 参考报告

> **来源**：[Anthropic Engineering — Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)（2025-11-24）

## 一、文章核心概述

Anthropic 发布了三项 Beta 特性，解决 AI Agent 在工具使用中的三大瓶颈：

| 特性 | 解决的问题 | 核心机制 | 效果 |
|------|-----------|---------|------|
| **Tool Search Tool** | 工具定义消耗过多 context tokens | 按需发现，延迟加载 | token 消耗减少 **85%**，准确率提升 25%+ |
| **Programmatic Tool Calling (PTC)** | 中间结果污染 context window | Claude 写代码编排工具调用 | token 减少 **37%**，消除多余推理轮次 |
| **Tool Use Examples** | JSON Schema 无法表达使用模式 | 在工具定义中嵌入示例 | 复杂参数准确率从 72% → **90%** |

---

## 二、三项特性详解

### 2.1 Tool Search Tool — 按需发现

**问题量化**：典型 5 个 MCP Server（GitHub/Slack/Sentry/Grafana/Splunk）= 58 个工具，~55K tokens。Anthropic 内部曾达到 **134K tokens** 仅用于工具定义。

**原理**：
1. 工具定义标记 `defer_loading: true`，不预加载到 context
2. Claude 仅看到 Tool Search Tool 本身（~500 tokens）+ 少量核心工具
3. 需要时通过 regex/BM25/embedding 搜索，按需加载 3-5 个相关工具（~3K tokens）
4. 总消耗从 ~77K tokens 降到 ~8.7K tokens

**关键配置**：
```json
{
  "tools": [
    {"type": "tool_search_tool_regex_20251119", "name": "tool_search_tool_regex"},
    {
      "name": "github.createPullRequest",
      "description": "Create a pull request",
      "input_schema": {...},
      "defer_loading": true
    }
  ]
}
```

**MCP 整库延迟加载**：
```json
{
  "type": "mcp_toolset",
  "mcp_server_name": "google-drive",
  "default_config": {"defer_loading": true},
  "configs": {
    "search_files": {"defer_loading": false}  // 高频工具保持加载
  }
}
```

**准确率提升**：
- Opus 4：49% → **74%**
- Opus 4.5：79.5% → **88.1%**

> [!IMPORTANT]
> Prompt caching 不受影响——deferred tools 完全排除在初始 prompt 之外。

---

### 2.2 Programmatic Tool Calling (PTC) — 代码编排

**问题**：传统工具调用的两个致命缺陷：
1. **Context 污染**：处理 10MB 日志时，整个文件进入 context，即使只需要错误频率统计
2. **推理开销**：每次工具调用需要一次完整推理，5 步工作流 = 5 次推理 + 人工综合

**原理**：Claude 写 Python 代码编排多个工具调用，中间结果在沙盒中处理，只有最终输出进入 context。

**典型场景**（预算合规检查）：

| | 传统方式 | PTC |
|---|---------|-----|
| 工具调用 | 20+ 独立调用，每次返回 context | 1 个代码块编排全部调用 |
| Context 消耗 | 200KB（2000+ 费用条目） | **1KB**（仅超额人员列表） |
| 推理轮次 | 20+ 次 | **1 次** |

**关键配置**：
```json
{
  "tools": [
    {"type": "code_execution_20250825", "name": "code_execution"},
    {
      "name": "get_team_members",
      "description": "Get all members of a department...",
      "input_schema": {...},
      "allowed_callers": ["code_execution_20250825"]
    }
  ]
}
```

**效果数据**：
- 平均 token：43,588 → **27,297**（↓37%）
- 知识检索准确率：25.6% → **28.5%**
- GIA 基准测试：46.5% → **51.2%**

---

### 2.3 Tool Use Examples — 示例学习

**问题**：JSON Schema 定义结构有效性，但无法表达：
- 日期格式应该用 `YYYY-MM-DD` 还是 `Nov 6, 2024`？
- ID 是 UUID 还是 `USR-12345`？
- 什么时候应该填充可选的嵌套字段？
- 不同参数之间的关联关系？

**原理**：在工具定义中加入 `input_examples` 字段，提供 1-5 个具体示例。

**示例设计原则**：
- 使用真实数据（真实城市名、合理价格），不用 `"string"` 占位
- 展示差异性：最小参数 / 部分参数 / 完整参数
- 聚焦歧义点（schema 已经足够清晰的参数不需要示例）

**效果**：准确率 72% → **90%**

---

## 三、最佳实践总结

### 分层策略

```
先诊断 → 再应用

Context 被工具定义撑爆？  → Tool Search Tool
中间数据太多干扰推理？    → Programmatic Tool Calling
工具调用参数经常出错？    → Tool Use Examples
```

### 工具描述质量

```json
// ✅ 好
{
  "name": "search_customer_orders",
  "description": "Search for customer orders by date range, status, or total amount. Returns order details including items, shipping, and payment info."
}

// ❌ 差
{
  "name": "query_db_orders",
  "description": "Execute order query"
}
```

### PTC 工具文档要求

对 `allowed_callers` 里的工具，description 必须清晰描述返回格式：

```json
{
  "name": "get_orders",
  "description": "Retrieve orders for a customer. Returns: List of order objects, each containing:\n- id (str): Order identifier\n- total (float): Order total in USD\n- status (str): One of 'pending', 'shipped', 'delivered'\n- items (list): Array of {sku, quantity, price}\n- created_at (str): ISO 8601 timestamp"
}
```

---

## 四、Vibe Center 项目应用分析

基于当前项目特点（Zsh CLI 工具、Agent 编排工作区、MCP 集成、Skills 系统），以下是具体应用方向：

### 4.1 Tool Search Tool → Skills 按需发现

**现状问题**：
- 项目有 **600+ skills** 列表加载到 context（参见系统 prompt 中长达数千行的 skills 列表）
- 每次对话开始，这些 skill 描述消耗大量 tokens
- Skill 选择时容易选错，尤其是名称相似的 skills

**应用方案**：

| 层级 | 当前做法 | 改进方向 |
|------|---------|---------|
| Skills 发现 | 全量加载到 system prompt | 按 `defer_loading: true` 延迟加载，仅保留 5-10 个核心 skills |
| Workflow 路由 | 全部 workflow 描述预加载 | 用 Tool Search Tool 按需搜索相关 workflow |
| MCP Server | 所有 MCP tool 预加载 | 按 server 级别 defer，保留高频工具 |

**具体实现思路**：
- 对 `.agents/skills/` 下的 600+ skills 建立搜索索引（名称 + 描述 + triggerKeywords）
- 核心保留（`defer_loading: false`）：`brainstorming`, `executing-plans`, `systematic-debugging`, `verification-before-completion`
- 其余全部 defer，通过搜索按需加载

> [!TIP]
> 这能将 skills 列表从占用 ~50K+ tokens 降到 ~5K tokens，释放出大量 context 空间。

---

### 4.2 Programmatic Tool Calling → 批量文件操作 & 分析

**现状问题**：
- `vibe check` / `vibe audit` 等命令需要遍历多个文件、汇总结果
- Agent 在分析代码库时，大量中间文件内容进入 context
- 多步 git 操作（diff → analyze → commit → push）每步都需要推理

**应用场景**：

| 场景 | 传统方式 | PTC 改进 |
|------|---------|---------|
| 代码审计 | 逐文件 view_file → 每个都进入 context | 写 Python 脚本批量读取，只返回问题列表 |
| Git Diff 分析 | 先 git diff → 全量进入 context → 再分析 | 代码中提取关键变更，只返回摘要 |
| 依赖检查 | 逐项检查 package.json → 累积结果 | 脚本并行检查，返回有问题的依赖 |
| 文档一致性检查 | 逐文件比对 | 脚本扫描全部 `.md` 文件，只返回不一致项 |

**对 `vibe-commit` Skill 的改进**：
- 当前：Agent 读取整个 `git diff` 到 context → 分析 → 生成 commit message
- 改进：PTC 脚本先分类统计变更（哪些文件、增减行数、变更类型），只将分类摘要返回给 Claude

---

### 4.3 Tool Use Examples → 提高工具调用准确性

**现状问题**：
- 项目 workflow 命令参数复杂（`/vibe-new`, `/opsx-ff`, `/vibe-commit` 等）
- MCP 工具的参数格式容易出错
- 类似工具的选择困难（`/opsx-new` vs `/opsx-ff` vs `/opsx-continue`）

**应用方案**：

为关键工具添加 `input_examples`：

```json
// 区分类似工具
{
  "name": "opsx-new",
  "description": "Start a new change with step-by-step artifacts",
  "input_examples": [
    {"change_name": "add-user-auth", "description": "Add OAuth2 authentication"}
  ]
},
{
  "name": "opsx-ff",
  "description": "Fast-forward: create all artifacts in one go",
  "input_examples": [
    {"change_name": "fix-typo-readme", "description": "Fix typo in README"}
  ]
}
```

> [!NOTE]
> 通过示例暗示：复杂功能用 `opsx-new`（分步），简单变更用 `opsx-ff`（快进）。

---

### 4.4 综合应用：下一代 Agent 架构

将三项特性结合，为 Vibe Center 的 Agent 系统设计分层架构：

```mermaid
graph TD
    A[用户请求] --> B{Tool Search Tool}
    B -->|搜索 Skills| C[按需加载 2-3 个相关 Skills]
    B -->|搜索 Workflows| D[加载匹配的 Workflow]
    C --> E{任务类型判断}
    D --> E
    E -->|批量数据处理| F[Programmatic Tool Calling]
    E -->|单步工具调用| G[传统 Tool Call + Examples]
    F --> H[代码编排：并行操作 + 数据过滤]
    G --> I[带 Examples 的精确调用]
    H --> J[只返回最终结果到 Context]
    I --> J
```

---

## 五、优先级建议

| 优先级 | 特性 | 应用场景 | 预期收益 | 实施难度 |
|--------|------|---------|---------|---------|
| **P0** | Tool Search Tool | Skills/Workflows 按需发现 | 减少 ~45K tokens/会话 | 低（API 配置） |
| **P1** | Tool Use Examples | 区分相似 workflows/tools | 减少误选率 30%+ | 低（添加示例） |
| **P2** | Programmatic Tool Calling | 代码审计、批量文件操作 | 减少 37% token 和推理轮次 | 中（需要设计编排逻辑） |

---

## 六、参考链接

- **文章原文**：[Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)
- **Tool Search Tool 文档**：[Documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) | [Cookbook](https://github.com/anthropics/claude-cookbooks/blob/main/tool_use/tool_search_with_embeddings.ipynb)
- **Programmatic Tool Calling 文档**：[Documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling) | [Cookbook](https://github.com/anthropics/claude-cookbooks/blob/main/tool_use/programmatic_tool_calling_ptc.ipynb)
- **Tool Use Examples 文档**：[Documentation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use#providing-tool-use-examples)
- **前置阅读**：[Building Effective Agents](https://www.anthropic.com/research/building-effective-agents) | [Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- **GIA Benchmark 论文**：[arXiv:2311.12983](https://arxiv.org/abs/2311.12983)
- **相关产品参考**：[Claude for Excel](https://www.claude.com/claude-for-excel)（PTC 实际应用案例）
- **灵感来源**：[LLMVM by Joel Pobar](https://github.com/9600dev/llmvm) | [Cloudflare Code Mode](https://blog.cloudflare.com/code-mode/)
- **Beta API 启用方式**：使用 header `betas=["advanced-tool-use-2025-11-20"]`
